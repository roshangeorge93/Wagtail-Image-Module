from __future__ import absolute_import, unicode_literals

from django.conf.urls import url

from wagtail.wagtailimages.views import chooser, images, multiple, folders
from wagtail.wagtailimages.api.custom import folders as folder_apis
from wagtail.wagtailimages.api.custom import images as image_apis

urlpatterns = [
    url(r'^$', images.custom_index, name='index'),
    url(r'^(\d+)/$', images.edit, name='edit'),
    url(r'^(\d+)/delete/$', images.delete, name='delete'),
    url(r'^(\d+)/generate_url/$', images.url_generator, name='url_generator'),
    url(r'^(\d+)/generate_url/(.*)/$', images.generate_url, name='generate_url'),
    url(r'^(\d+)/preview/(.*)/$', images.preview, name='preview'),
    url(r'^add/$', images.add, name='add'),
    url(r'^usage/(\d+)/$', images.usage, name='image_usage'),

    url(r'^multiple/add/$', multiple.add, name='add_multiple'),
    url(r'^multiple/(\d+)/$', multiple.edit, name='edit_multiple'),
    url(r'^multiple/(\d+)/delete/$', multiple.delete, name='delete_multiple'),

    url(r'^folder/add/$', folders.add, name='add_folder'),
    url(r'^folder/add/(\d+)/$', folders.add, name='add_folder_to_folder'),
    url(r'^folder/delete/(\d+)/$', folders.delete, name='delete_folder'),
    url(r'^folder/(\d+)/$', folders.edit, name='edit_folder'),

    url(r'^chooser/$', chooser.chooser, name='chooser'),
    url(r'^chooser/(\d+)/$', chooser.image_chosen, name='image_chosen'),
    url(r'^chooser/upload/$', chooser.chooser_upload, name='chooser_upload'),
    url(r'^chooser/(\d+)/select_format/$', chooser.chooser_select_format, name='chooser_select_format'),

    url(r'^custom-api/folders/move/$', folder_apis.move, name='move_api'),
    url(r'^custom-api/folders/(\d+)/delete/$', folder_apis.delete, name='delete_folder_api'),

    url(r'^custom-api/images/(\d+)/delete/$', image_apis.delete, name='delete_image_api'),
]
