import os
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from wagtail.wagtailimages.models import get_folder_model
from wagtail.wagtailimages.permissions import permission_policy
from wagtail.wagtailimages.utils import get_folders_list, create_db_entries
from wagtail.wagtailimages import get_image_model
from wagtail.wagtailsearch import index as search_index

ImageFolder = get_folder_model()
Image = get_image_model()


def list(request, folder_id=None):

    if not permission_policy.user_has_any_permission(request.user, ['add', 'change', 'delete']):
        response = {
            'message': "User does not have permission"
        }
        return JsonResponse(response, status=403)

    if folder_id:
        folders = ImageFolder.objects.filter(id=folder_id)
    else:
        folders = ImageFolder.objects.filter(folder__isnull=True)

    folders_list = get_folders_list(folders)
    return JsonResponse(folders_list, safe=False)


@require_POST
def add(request, parent_id=None):
    response = dict()

    if not permission_policy.user_has_permission(request.user, 'add'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    title = request.POST.get('title')

    if not title:
        response['message'] = "Title missing"
        return JsonResponse(response, status=400)

    parent_folder = None
    if parent_id:
        try:
            parent_folder = ImageFolder.objects.get(id=parent_id)
        except ObjectDoesNotExist:
            response['message'] = "Invalid Parent ID"
            return JsonResponse(response, status=404)

    if parent_folder:
        if ImageFolder.objects.filter(folder=parent_folder, title=title).count() > 0:
            response['message'] = "Folder already exists"
            return JsonResponse(response, status=403)
    else:
        if ImageFolder.objects.filter(folder__isnull=True, title=title).count() > 0:
            response['message'] = "Folder already exists"
            return JsonResponse(response, status=403)

    # Save folder
    folder = ImageFolder(
        title=title
    )
    if parent_folder:
        folder.folder = parent_folder
    folder.save()

    folder_dict = dict()
    folder_dict['id'] = folder.id
    folder_dict['title'] = folder.title

    response['message'] = "Success"
    response['data'] = folder_dict
    return JsonResponse(response)


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

    try:
        target_folder = ImageFolder.objects.get(id=target_id)
    except ObjectDoesNotExist:
        response['message'] = "Invalid target ID"
        return JsonResponse(response, status=404)

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
        new_path = os.path.join(target_folder.path, complete_file_name)
        while True:
            # Keeping renaming in a loop to handle multiple filename clashes
            if os.path.exists(new_path):
                count += 1
                complete_file_name = file_name + str(count) + extension
                new_path = os.path.join(target_folder.path, complete_file_name)
            else:
                os.rename(initial_path, new_path)
                if count:
                    image.title = image.title + str(count)
                break

        image.file.name = os.path.join(target_folder.path, complete_file_name)
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
                    response['new_folders'] = folders_list
                    # Return a 202 as the intended action was not completed
                    return JsonResponse(response, status=202)
            else:
                break
        source_folder.save()
        response['new_source_name'] = source_folder.title

    else:
        response['message'] = "Invalid source type"
        return JsonResponse(response, status=400)

    response['message'] = "Success"
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
    title = request.POST.get('title', folder.title)

    parent_folder = None
    parent_id = request.POST.get('parent_id')
    if parent_id:
        try:
            parent_folder = ImageFolder.objects.get(id=parent_id)
        except ObjectDoesNotExist:
            response['message'] = "Invalid Parent ID"
            return JsonResponse(response, status=404)

    if parent_folder:
        if ImageFolder.objects.filter(folder=parent_folder, title=title).count() > 0:
            response['message'] = "Folder already exists"
            return JsonResponse(response, status=403)
    else:
        if ImageFolder.objects.filter(folder__isnull=True, title=title).count() > 0:
            response['message'] = "Folder already exists"
            return JsonResponse(response, status=403)

    folder.title = title
    if parent_folder:
        folder.folder = parent_folder
    folder.folder = request.POST.get('parent_id', folder.folder)
    folder.save()

    response['message'] = "Success"
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
