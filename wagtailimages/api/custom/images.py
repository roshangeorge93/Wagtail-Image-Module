import os
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist

from wagtail.wagtailimages.models import get_folder_model
from wagtail.wagtailimages.permissions import permission_policy
from wagtail.wagtailimages import get_image_model

ImageFolder = get_folder_model()
Image = get_image_model()


@require_POST
def move(request):
    response = dict()

    if not permission_policy.user_has_permission(request.user, 'change'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    image_id = request.POST.get('image_id')
    folder_id = request.POST.get('folder_id')

    if not image_id or not folder_id:
        response['message'] = "Image or folder ID missing"
        return JsonResponse(response, status=400)

    try:
        image = Image.objects.get(id=image_id)
    except ObjectDoesNotExist:
        response['message'] = "Invalid Image ID"
        return JsonResponse(response, status=404)

    try:
        folder = ImageFolder.objects.get(id=folder_id)
    except ObjectDoesNotExist:
        response['message'] = "Invalid Folder ID"
        return JsonResponse(response, status=404)


    if not permission_policy.user_has_permission_for_instance(request.user, 'change', image):
        response['message'] = "Sorry, you do not have permission to access this area."
        return JsonResponse(response, status=403)

    initial_path = image.file.path

    image.folder = folder
    # Change the path of the file
    image.file.name = os.path.join(folder.path, image.filename)
    image.save()

    new_path = image.file.path
    os.rename(initial_path, new_path)

    response['message'] = "Success"
    return JsonResponse(response)


@require_POST
def add(request):
    response = dict()

    if not permission_policy.user_has_permission(request.user, 'change'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    title = request.POST.get('title')
    file = request.FILES.get('files[]')

    if not title or not file:
        response['message'] = "Title or file missing"
        return JsonResponse(response, status=400)

    image = Image()
    image.title = title
    image.file = file

    folder_id = request.POST.get('folder_id')
    if folder_id:
        try:
            folder = ImageFolder.objects.get(id=folder_id)
            image.folder = folder
        except ObjectDoesNotExist:
            response['message'] = "Invalid Folder ID"
            return JsonResponse(response, status=404)

    image.save()

    image_dict = dict()
    image_dict
    response['message'] = "Success"
    return JsonResponse(response)


def search(request):
    response = dict()

    if not permission_policy.user_has_any_permission(request.user, ['add', 'change', 'delete']):
        response = {
            'message': "User does not have permission"
        }
        return JsonResponse(response, status=403)

    # Get images (filtered by user permission)
    images = permission_policy.instances_user_has_any_permission_for(
        request.user, ['change', 'delete']
    ).order_by('-created_at')

    # Search
    query_string = None
    if 'query_string' in request.GET:
        query_string = request.GET.get('query_string')
        images = images.search(query_string)
    else:
        response['message'] = "No query string passed"
        return JsonResponse(response, status=400)

    # Filter by folder
    current_folder = None
    folder_id = request.GET.get('folder_id')
    if folder_id:
        try:
            current_folder = ImageFolder.objects.get(id=folder_id)
            images = images.filter(folder=current_folder)
        except ObjectDoesNotExist:
            response['message'] = "Invalid Folder ID"
            return JsonResponse(response, status=400)

    image_list = list()
    for image in images:
        image_dict = dict()
        image_dict['id'] = image.id
        image_dict['title'] = image.title
        image_dict['url'] = image.file.path
        image_list.append(image_dict)

    return JsonResponse(image_list, safe=False)
