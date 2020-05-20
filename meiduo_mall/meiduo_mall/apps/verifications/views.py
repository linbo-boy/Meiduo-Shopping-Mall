from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from django_redis import get_redis_connection
from rest_framework.views import APIView

from meiduo_mall.libs.captcha.captcha import captcha
from . import constants


class ImageCodeView(APIView):
    def get(self, request, image_code_id):
        """
        图片验证码
        :param request: GET /image_codes/(?P<image_code_id>[\w-]+)/
        :param image_code_id: 图片验证码编号
        :return: 验证码图片
        """
        # 1.生成图片验证码
        text, image = captcha.generate_captcha()
        # 2.保存真实值
        redis_conn = get_redis_connection('verify_codes')
        redis_conn.setex('img_%s' % image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)
        # 3.返回图片
        return HttpResponse(image, content_type="images/jpg")
