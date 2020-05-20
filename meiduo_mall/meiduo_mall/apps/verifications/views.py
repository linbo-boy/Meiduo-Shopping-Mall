from random import random

from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
import logging

from meiduo_mall.libs.captcha.captcha import captcha
from . import constants
from .serializers import ImageCodeCheckSerializer
from meiduo_mall.utils.yuntongxun.sms import CCP


logger = logging.getLogger('django')


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


class SMSCodeView(GenericAPIView):
    """
    短信验证码
    传入参数：
        mobile, image_code_id, text
    """
    serializer_class = ImageCodeCheckSerializer

    def get(self, request, mobile):
        # 1.检查图片验证码,由序列化器完成
        serializer = self.get_serializer(data=request.query_params)
        # 2.检查是否在60s内有发送记录
        serializer.is_valid(raise_exception=True)
        # 3.生成短信验证码
        sms_code = '%06d' % random.randint(0, 999999)
        # 4.保存短信验证码与发送记录
        redis_conn = get_redis_connection('verify_codes')
        # redis_conn.setex("sms_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        # redis_conn.setex("send_flag_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)

        # redis管道
        p1 = redis_conn.pipeline()
        p1.setex("sms_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        p1.setex("send_flag_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)
        # 让管道通知redis执行命令
        p1.execute()

        # 5.发送短信
        try:
            ccp = CCP()
            expires = str(constants.SMS_CODE_REDIS_EXPIRES // 60)
            result = ccp.send_template_sms(mobile, [sms_code, expires], constants.SMS_CODE_TEMP_ID)
        except Exception as e:
            logger.error("发送验证码短信[异常][ mobile: %s, message: %s ]" % (mobile, e))
            return Response({"message": "Failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            if result == 0:
                logger.info("发送验证码短信[正常][ mobile: %s ]" % mobile)
                return Response({"message": "OK"})
            else:
                logger.warning("发送验证码短信[失败][ mobile: %s ]" % mobile)
                return Response({"message": "Failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
