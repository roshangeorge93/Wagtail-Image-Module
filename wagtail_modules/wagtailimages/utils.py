from __future__ import absolute_import, unicode_literals

import os

from wagtail.wagtailsearch import index as search_index
from wagtail.wagtailimages.models import get_folder_model
from wagtail.wagtailimages.forms import get_image_form
from wagtail.wagtailimages.fields import ALLOWED_EXTENSIONS
from wagtail.wagtailimages import get_image_model

from django.core.files import File

ImageFolder = get_folder_model()
Image = get_image_model()
ImageForm = get_image_form(Image)


# Helper functions for migrating the Rendition.filter foreign key to the filter_spec field,
# and the corresponding reverse migration

def get_fill_filter_spec_migrations(app_name, rendition_model_name):

    def fill_filter_spec_forward(apps, schema_editor):
        # Populate Rendition.filter_spec with the spec string of the corresponding Filter object
        Rendition = apps.get_model(app_name, rendition_model_name)
        Filter = apps.get_model('wagtailimages', 'Filter')

        db_alias = schema_editor.connection.alias
        for flt in Filter.objects.using(db_alias):
            renditions = Rendition.objects.using(db_alias).filter(filter=flt, filter_spec='')
            renditions.update(filter_spec=flt.spec)

    def fill_filter_spec_reverse(apps, schema_editor):
        # Populate the Rendition.filter field with Filter objects that match the spec in the
        # Rendition's filter_spec field
        Rendition = apps.get_model(app_name, rendition_model_name)
        Filter = apps.get_model('wagtailimages', 'Filter')
        db_alias = schema_editor.connection.alias

        while True:
            # repeat this process until we've confirmed that no remaining renditions exist with
            # a null 'filter' field - this minimises the possibility of new ones being inserted
            # by active server processes while the query is in progress

            # Find all distinct filter_spec strings used by renditions with a null 'filter' field
            unmatched_filter_specs = Rendition.objects.using(db_alias).filter(
                filter__isnull=True).values_list('filter_spec', flat=True).distinct()
            if not unmatched_filter_specs:
                break

            for filter_spec in unmatched_filter_specs:
                filter, _ = Filter.objects.using(db_alias).get_or_create(spec=filter_spec)
                Rendition.objects.using(db_alias).filter(filter_spec=filter_spec).update(filter=filter)

    return (fill_filter_spec_forward, fill_filter_spec_reverse)


def create_db_entries(title, user, parent_folder=None):
    """Recursively creates DB entries for a physical folder, its sub folders
    and images under them."""

    folder = ImageFolder()
    folder.title = title
    if parent_folder:
        folder.folder = parent_folder

    try:
        folder.save()
    except FileExistsError:
        # Ignore the exception as the physical folder already exists
        pass

    complete_path = folder.get_complete_path()

    for entry in os.listdir(complete_path):
        # Get all the files and folders under the current folder
        # If a file is found and if its of an image type, create an image entry
        if os.path.isfile(os.path.join(complete_path, entry)):
            extension = os.path.splitext(entry)[1]  # get the extension
            extension = extension[1:]   # Remove the '.' from the extension
            if extension in ALLOWED_EXTENSIONS:
                create_image(entry, user, folder)

        # Recursively do the same for the sub folders
        if os.path.isdir(os.path.join(complete_path, entry)):
            create_db_entries(entry, user, folder)

    return folder


def create_image(file_name, user, folder):
    """Creates an image object."""

    image_file = File(open(os.path.join(folder.get_complete_path(), file_name), 'rb'))

    # Build a form for validation
    form = ImageForm({
        'title': os.path.splitext(file_name)[0],
        'collection': '1',  # Hard coding the root collection as default
    }, {
        'file': image_file
    }, user=user)

    if form.is_valid():
        # Save it
        image = form.save(commit=False)
        image.uploaded_by_user = user
        image.file_size = image.file.size
        image.folder = folder
        image.save()

        # Reindex the image to make sure all tags are indexed
        search_index.insert_or_update_object(image)

        return image
    return None


def get_folders_list(folders):
    """Recursively converts a list of folder objects to a list of folder dicts.
    Also returns a list of images under each folder in a dictionary format."""

    folders_list = list()
    for folder in folders:
        folder_dict = dict()
        folder_dict['id'] = folder.id
        folder_dict['title'] = folder.title

        # Add images
        folder_dict['images'] = list()
        images = Image.objects.filter(folder=folder)
        for image in images:
            folder_dict['images'].append(get_image_dict(image))

        # Get the contents of the sub folder
        folder_dict['sub_folders'] = get_folders_list(folder.get_subfolders())
        folders_list.append(folder_dict)
    return folders_list


def get_image_dict(image):
    """Converts an image object to dictionary containing the core fields of an image."""

    image_dict = dict()
    image_dict['id'] = image.id
    image_dict['title'] = image.title
    image_dict['url'] = image.file.url
    return image_dict
