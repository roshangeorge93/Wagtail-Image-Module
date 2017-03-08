from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist

from wagtail.wagtailimages.models import get_folder_model
from wagtail.wagtailimages.permissions import permission_policy
from wagtail.wagtailimages import get_image_model
from wagtail.wagtailsearch import index as search_index

ImageFolder = get_folder_model()
Image = get_image_model()


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


@require_POST
def delete(request, image_id):
    response = dict()

    if not permission_policy.user_has_permission(request.user, 'change'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    try:
        image = Image.objects.get(id=image_id)
    except ObjectDoesNotExist:
        response['message'] = "Invalid ID"
        return JsonResponse(response, status=404)

    image.delete()

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
