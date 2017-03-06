from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist

from wagtail.wagtailimages.models import get_folder_model
from wagtail.wagtailimages.permissions import permission_policy
from wagtail.wagtailimages import get_image_model


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


def get_folders_list(folders):
    folders_list = list()
    for folder in folders:
        folder_dict = dict()
        folder_dict['id'] = folder.id
        folder_dict['title'] = folder.title

        # Add images
        folder_dict['images'] = list()
        images = Image.objects.filter(folder=folder)
        for image in images:
            image_dict = dict()
            image_dict['id'] = image.id
            image_dict['title'] = image.title
            image_dict['url'] = image.file.path

        # Get the contents of the sub folder
        folder_dict['sub_folders'] = get_folders_list(folder.get_subfolders())
        folders_list.append(folder_dict)
    return folders_list


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
