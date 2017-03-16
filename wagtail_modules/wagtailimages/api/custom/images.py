import os
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist

from wagtail.wagtailimages.models import get_folder_model
from wagtail.wagtailimages.permissions import permission_policy
from wagtail.wagtailimages import get_image_model
from wagtail.wagtailsearch import index as search_index
from wagtail.wagtailimages.utils import get_image_dict
from wagtail.wagtailimages.forms import get_image_form
from wagtail.wagtailimages.fields import ALLOWED_EXTENSIONS

ImageFolder = get_folder_model()
Image = get_image_model()
ImageForm = get_image_form(Image)


@require_POST
def add(request):
    response = dict()

    if not permission_policy.user_has_permission(request.user, 'change'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    file = request.FILES.get('files[]')
    title = os.path.splitext(file.name)[0]

    if not title or not file:
        response['message'] = "Title or file missing"
        return JsonResponse(response, status=400)

    extension = os.path.splitext(file.name)[1]
    extension = extension[1:]   # Remove the '.' from the extension

    if extension not in ALLOWED_EXTENSIONS:
        response['message'] = "Invalid file type"
        return JsonResponse(response, status=400)

    folder = None
    folder_id = request.POST.get('folder_id')
    if folder_id and int(folder_id) != -1:
        try:
            folder = ImageFolder.objects.get(id=folder_id)
        except ObjectDoesNotExist:
            response['message'] = "Invalid Folder ID"
            return JsonResponse(response, status=404)

    # Build a form for validation
    form = ImageForm({
        'title': title,
        'collection': '1',  # Hard coding the root collection as default
    }, {
        'file': file
    }, user=request.user)

    if form.is_valid():
        # Save it
        image = form.save(commit=False)
        image.uploaded_by_user = request.user
        image.file_size = image.file.size
        image.folder = folder
        image.save()

        # Reindex the image to make sure all tags are indexed
        search_index.insert_or_update_object(image)

        response['data'] = get_image_dict(image)
        response['message'] = "Success"
    else:
        response['message'] = "Error creating image"
        # ToDo send a valid respone based on the error
        response['data'] = None
    return JsonResponse(response)


@require_POST
def edit(request, image_id):
    response = dict()

    if not permission_policy.user_has_permission(request.user, 'change'):
        response['message'] = "User does not have permission"
        return JsonResponse(response, status=403)

    try:
        image = Image.objects.get(id=image_id)
    except ObjectDoesNotExist:
        response['message'] = "Invalid ID"
        return JsonResponse(response, status=404)

    title = request.POST.get('title')
    if title:
        image.title = title
        image.save()
        search_index.insert_or_update_object(image)
        response['message'] = "Success"
        response['data'] = get_image_dict(image)
        return JsonResponse(response)
    else:
        response['message'] = "Title not passed"
        return JsonResponse(response, status=400)


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
        image_list.append(get_image_dict(image))

    return JsonResponse(image_list, safe=False)
