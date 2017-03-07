import os

from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError
from django.core.files import File

from wagtail.wagtailadmin.utils import PermissionPolicyChecker
from wagtail.wagtailimages.permissions import permission_policy
from wagtail.wagtailsearch import index as search_index
from wagtail.wagtailimages.fields import ALLOWED_EXTENSIONS
from wagtail.wagtailimages.models import get_folder_model
from wagtail.wagtailimages.forms import get_folder_form
from wagtail.wagtailimages import get_image_model
from wagtail.wagtailimages.forms import get_image_form
permission_checker = PermissionPolicyChecker(permission_policy)
ImageFolder = get_folder_model()
ImageFolderForm = get_folder_form(ImageFolder)
Image = get_image_model()


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

    ImageForm = get_image_form(Image)
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



@permission_checker.require('add')
def add(request, add_to_folder=False):

    parent_folder = False
    if add_to_folder:
        parent_folder = get_object_or_404(ImageFolder, id=add_to_folder)

    if request.method == 'POST':
        # Build a form for validation
        form = ImageFolderForm(request.POST)
        error = True

        if form.is_valid():
            error = False

            folder = ImageFolder(
                title=form.cleaned_data['title'].strip()
            )
            if parent_folder:
                folder.folder = parent_folder

            try:
                # Check if the folder is present in the DB or physically present in the OS
                folder.validate_folder()
            except ValidationError as e:
                if e.code == 'os':
                    folder = create_db_entries(form.cleaned_data['title'].strip(), request.user, parent_folder)
                else:
                    error = True
                    form._errors['title'] = e.message
            else:
                # Save folder
                folder.save()

        if not error:
            # Success! Send back to index or image specific folder
            response = redirect('wagtailimages:index')
            response['Location'] += '?folder={0}'.format(folder.id)
            return response
        else:
            # Validation error
            return render(request, 'wagtailimages/folder/add.html', {
                'error_message': 'Error adding folder',
                'help_text': '',
                'parent_folder': parent_folder,
                'form': form,
            })
    else:
        form = ImageFolderForm()

        return render(request, 'wagtailimages/folder/add.html', {
            'help_text': '',
            'parent_folder': parent_folder,
            'form': form,
        })


@permission_checker.require('change')
def edit(request, folder_id):
    folder = get_object_or_404(ImageFolder, id=folder_id)

    if request.method == 'POST':
        # Build a form for validation
        form = ImageFolderForm(request.POST)

        if form.is_valid():

            folder.title = form.cleaned_data['title']

            try:
                # Check if the folder is present in the DB or physically present in the OS
                folder.validate_folder()
            except ValidationError as e:
                form._errors['title'] = e.message
                # Validation error
                return render(request, 'wagtailimages/folder/edit.html', {
                    'error_message': 'Error adding folder',
                    'help_text': '',
                    'form': form,
                })

            folder.save()

            # Success! Send back to index or image specific folder
            response = redirect('wagtailimages:index')
            response['Location'] += '?folder={0}'.format(folder.id)
            return response
        else:
            # Validation error
            return render(request, 'wagtailimages/folder/edit.html', {
                'error_message': 'Error adding folder',
                'help_text': '',
                'form': form,
            })
    else:
        form = ImageFolderForm(instance=folder)

    return render(request, 'wagtailimages/folder/edit.html', {
        'help_text': '',
        'folder': folder,
        'form': form,
    })


@permission_checker.require('change')
def delete(request, folder_id):
    folder = get_object_or_404(ImageFolder, id=folder_id)

    if request.method == 'POST':
        # POST if confirmation of delete

        # try find a parent folder
        parent_folder = folder.get_parent()

        # Delete folder
        folder.delete()

        # Success! Send back to index or image specific folder
        response = redirect('wagtailimages:index')
        if parent_folder:
            response['Location'] += '?folder={0}'.format(parent_folder.id)
        return response

    return render(request, 'wagtailimages/folder/confirm_delete.html', {
        'folder': folder,
        # 'form': form,
    })
