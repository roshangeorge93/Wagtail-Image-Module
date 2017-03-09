import os

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from wagtail.wagtailimages.models import get_folder_model, IMAGES_FOLDER_NAME
from wagtail.wagtailimages.permissions import permission_policy
from wagtail.wagtailimages.utils import (
    get_folders_list,
    create_db_entries,
    get_image_dict
)
from wagtail.wagtailimages import get_image_model
from wagtail.wagtailsearch import index as search_index

ImageFolder = get_folder_model()
Image = get_image_model()


def list(request, folder_id=None):
    """Returns a list of folders and images under them in JSON compatible format.
    Optional folder id can be passed to get folders and images under a specific folder.
    """

    if not permission_policy.user_has_any_permission(request.user, ['add', 'change', 'delete']):
        response = {
            'message': "User does not have permission"
        }
        return JsonResponse(response, status=403)

    if folder_id:
        folders = ImageFolder.objects.filter(id=folder_id)
        folders_list = get_folders_list(folders)
    else:
        root_folder = dict()
        root_folder['id'] = '-1'
        root_folder['title'] = 'root'

        # Get all folders under root
        folders = ImageFolder.objects.filter(folder__isnull=True)
        root_folder['sub_folders'] = get_folders_list(folders)

        # Get all images under root
        images = Image.objects.filter(folder__isnull=True)
        root_folder['images'] = list()
        for image in images:
            root_folder['images'].append(get_image_dict(image))

        folders_list = [root_folder]

    return JsonResponse(folders_list, safe=False)


@require_POST
def move(request):
    response = dict()
    if not permission_policy.user_has_permission(request.user, 'change'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    source_id = request.POST.get('source_id')
    target_id = request.POST.get('target_id')
    source_type = request.POST.get('source_type')
    count = 0   # Indicates number of attempts to rename a file/folder

    if not source_id or not target_id or not source_type:
        response['message'] = "Image or folder ID missing"
        return JsonResponse(response, status=400)

    if target_id == -1:
        target_folder = None   # Root folder
        target_absolute_path = os.path.join(settings.MEDIA_ROOT, IMAGES_FOLDER_NAME)
        target_relative_path = IMAGES_FOLDER_NAME
    else:
        try:
            target_folder = ImageFolder.objects.get(id=target_id)
        except ObjectDoesNotExist:
            response['message'] = "Invalid target ID"
            return JsonResponse(response, status=404)
        else:
            target_absolute_path = target_folder.get_complete_path()
            target_relative_path = target_folder.path

    if source_type == 'image':
        try:
            image = Image.objects.get(id=source_id)
        except ObjectDoesNotExist:
            response['message'] = "Invalid source ID"
            return JsonResponse(response, status=404)

        image.folder = target_folder   # Change the folder

        # Move the file to the updated location
        # When moving a file to a new location, check if a file
        # with the same name exists.
        # If yes, then append a number to the filename and save
        initial_path = image.file.path
        complete_file_name = image.filename
        file_name = os.path.splitext(image.filename)[0]     # get the filename
        extension = os.path.splitext(image.filename)[1]     # get the extension
        new_path = os.path.join(target_absolute_path, complete_file_name)
        while True:
            # Keeping renaming until there are no more filename clashes
            if os.path.exists(new_path):
                count += 1
                complete_file_name = file_name + str(count) + extension
                new_path = os.path.join(target_absolute_path, complete_file_name)
            else:
                os.rename(initial_path, new_path)
                if count:
                    # If there were attempts made to resolve conflict,
                    # change the image's title
                    # Append the count to the title
                    image.title = image.title + str(count)
                    response['message'] = "File with the same name exists! Renaming to avoid conflict."
                else:
                    response['message'] = "Success"
                break

        image.file.name = os.path.join(target_relative_path, complete_file_name)
        image.save()
        search_index.insert_or_update_object(image)
        response['new_source_name'] = image.title

    elif source_type == 'folder':
        try:
            source_folder = ImageFolder.objects.get(id=source_id)
        except ObjectDoesNotExist:
            response['message'] = "Invalid Folder ID"
            return JsonResponse(response, status=404)

        source_folder.folder = target_folder
        while True:
            try:
                # Check if the folder is present in the DB or physically present in the OS
                source_folder.validate_folder()
            except ValidationError as e:
                count += 1
                if e.code == 'db':
                    source_folder.title = source_folder.title + str(count)
                else:
                    # When a folder with a clashing name exists in the OS,
                    # Add the entry to the DB and notify the user.
                    # Abort the current move operation
                    new_folder = create_db_entries(source_folder.title, request.user, target_folder)
                    folders_list = get_folders_list([new_folder])
                    response['message'] = "Operation Failed! Found new entry in the OS. Loading the folder..."
                    response['new_folder'] = folders_list[0]
                    # Return a 202 as the intended action was not completed
                    return JsonResponse(response, status=202)
            else:
                if count:
                    # If there were attempts made to resolve conflict
                    response['message'] = "Folder with the same name exists! Renaming to avoid conflict."
                else:
                    response['message'] = "Success"
                break
        source_folder.save()
        response['new_source_name'] = source_folder.title
        return JsonResponse(response)
    else:
        response['message'] = "Invalid source type"
        return JsonResponse(response, status=400)



@require_POST
def add(request, parent_id=None):
    response = dict()

    if not permission_policy.user_has_permission(request.user, 'add'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    title = request.POST.get('title')

    if not title:
        response['message'] = "Title not passed"
        return JsonResponse(response, status=400)

    parent_folder = None
    if parent_id:
        try:
            parent_folder = ImageFolder.objects.get(id=parent_id)
        except ObjectDoesNotExist:
            response['message'] = "Invalid Parent ID"
            return JsonResponse(response, status=404)

    # Save folder
    folder = ImageFolder(
        title=title
    )
    if parent_folder:
        folder.folder = parent_folder
    try:
        # Check if the folder is present in the DB or physically present in the OS
        folder.validate_folder()
    except ValidationError as e:
        if e.code == 'os':
            # If present in the OS, then create the folder entry and it's
            # content's entries in the DB
            folder = create_db_entries(title, request.user, parent_folder)
            folders_list = get_folders_list([folder])
            response['message'] = "Found new entry in the OS! Loading the folder..."
            response['data'] = folders_list[0]
        else:
            response['message'] = "Folder already exists"
            return JsonResponse(response, status=403)
    else:
        # Save folder
        folder.save()
        response['message'] = "Success"
        response['data'] = get_folders_list([folder])[0]

    return JsonResponse(response)


@require_POST
def edit(request, folder_id):
    response = dict()

    if not permission_policy.user_has_permission(request.user, 'change'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    try:
        folder = ImageFolder.objects.get(id=folder_id)
    except ObjectDoesNotExist:
        response['message'] = "Invalid ID"
        return JsonResponse(response, status=404)

    parent_folder = None
    parent_id = request.POST.get('parent_id')
    if parent_id:
        try:
            parent_folder = ImageFolder.objects.get(id=parent_id)
        except ObjectDoesNotExist:
            response['message'] = "Invalid Parent ID"
            return JsonResponse(response, status=404)

    title = request.POST.get('title', folder.title)
    folder.title = title
    if parent_folder:
        folder.folder = parent_folder
    count = 0   # Indicates the number of times the folder name clashed
    while True:
        try:
            # Check if the folder is present in the DB or physically present in the OS
            folder.validate_folder()
        except ValidationError as e:
            count += 1
            if e.code == 'db':
                folder.title = folder.title + str(count)
            else:
                # When a folder with a clashing name exists in the OS,
                # Add the entry to the DB and notify the user.
                # Abort the current move operation
                new_folder = create_db_entries(title, request.user, parent_folder)
                folders_list = get_folders_list([new_folder])
                response['message'] = "Operation Failed! Found new entry in the OS. Loading the folder..."
                response['data'] = folders_list[0]
                # Return a 202 as the intended action was not completed
                return JsonResponse(response, status=202)
        else:
            if count:
                # If there were attempts made to resolve conflict
                response['message'] = "Folder with the same name exists! Renaming to avoid conflict."
            else:
                response['message'] = "Success"
            break

    response['data'] = get_folders_list([folder])[0]
    return JsonResponse(response)


@require_POST
def delete(request, folder_id):
    response = dict()

    if not permission_policy.user_has_permission(request.user, 'change'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    try:
        folder = ImageFolder.objects.get(id=folder_id)
    except ObjectDoesNotExist:
        response['message'] = "Invalid ID"
        return JsonResponse(response, status=404)

    # Delete folder
    folder.delete()

    response['message'] = "Success"
    return JsonResponse(response)
