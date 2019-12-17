# -*- coding: utf-8 -*-
"""
Project: HelloWorldPython
Creator: DoubleThunder
Create time: 2019-09-28 12:18
Introduction: 微信防撤回功能
微信防撤回功能。
（先确定你的微信号能登录网页版微信）
实现功能：
1. 监听所有的消息（好友，群组）保存于字典中，非文字消息，保存文件到缓存文件夹。
2. 监听系统公告通知，如果有好友撤回消息。而从字典中取出数据，发送到你的『文件传输助手』中。
    如果你将 is_auto_forward = True，撤回的消息会即可发送给好友或群组。

此项目需要的库有：itchat，apscheduler

"""
import base64
import os
# import pprint
import re
import shutil
import subprocess
import time
from urllib.parse import unquote

import cv2
import itchat
import math
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from itchat.content import *

import options
import random

# import pysnooper

# 自己的uid
global_vars = {
    'me_uid': ''
}

# 文件临时存储地址
rec_tmp_dir = os.path.join(os.getcwd(), 'tmp', 'revoke')

# 存储数据的字典
rec_msg_dict = {}

# 判断消息是否为撤回消息公告(包括了简体|繁体|英文)
revoke_msg_compile = r'^<sysmsg type="revokemsg">[\n\t]*<revokemsg>[\n\t]*<session>(.*?)<\/session>[\n\t]*<oldmsgid>.*?<\/oldmsgid>[\n\t]*<msgid>(.*?)<\/msgid>.*?"(.*?)"\s(?:撤回了一条消息|已回收一條訊息|recalled a message)'

# 用于定时清理缓存数据
scheduler = BackgroundScheduler()

# 消息类型的中文名称，与转发标识
content_type_dict = {
    'Text': {'name': '文字', 'code': '@msg@'},
    'Map': {'name': '地图', 'code': '@msg@'},
    'Card': {'name': '名片', 'code': '@msg@'},
    'Note': {'name': '系统消息', 'code': '@msg@'},
    'Sharing': {'name': '分享', 'code': '@msg@'},
    'Picture': {'name': '图片', 'code': '@img@'},
    'Recording': {'name': '语音', 'code': '@fil@'},
    'Attachment': {'name': '附件', 'code': '@fil@'},
    'Video': {'name': '视频', 'code': '@vid@'},
    'Friends': {'name': '好友邀请', 'code': '@msg@'},
    'System': {'name': '系统', 'code': '@msg@'}
}


def get_xiaobing_response(_info):
    url = f'https://www4.bing.com/socialagent/chat?q={_info}&anid=123456'
    try:
        response = requests.get(url)
        try:
            res = response.json()
            reply = unquote(res['InstantMessage']['ReplyText'])
            return reply
        except Exception as e2:
            print(e2)
    except Exception as e1:
        print(e1)
    return options.DEFAULT_REPLY


def mark_face_baidu_api(file_path, to_user_name):
    host = 'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=GFx4vMqk6kslchni22WlLHsC&client_secret=7juflRO0Rf7m5ZZ3OcVyotvNTBLXKann'
    header = {'Content-Type': 'application/json; charset=UTF-8'}
    response = requests.post(url=host, headers=header)  # <class 'requests.models.Response'>
    if response.status_code != 200:
        print('请求错误')
        return
    access_token = response.json()['access_token']
    with open(file_path, 'rb') as f:
        pic = base64.b64encode(f.read())
        image = str(pic, 'utf-8')
    request_url = "https://aip.baidubce.com/rest/2.0/face/v3/detect"
    params = {"image": image, "image_type": "BASE64", "max_face_num": 10,
              "face_field": "age,beauty,expression,faceshape,gender,glasses,landmark,race,qualities"}
    header = {'Content-Type': 'application/json'}
    request_url = request_url + "?access_token=" + access_token
    result = requests.post(url=request_url, data=params, headers=header).json()
    if result:
        if "result" in result and result["result"]:
            if "face_num" in result["result"]:
                face_num = result["result"]["face_num"]
                faces = result["result"]["face_list"]
                reply = f'共发现{face_num}张脸:\n'
                ret_image = cv2.imread(file_path)
                for face in faces:
                    face_prob = face["face_probability"]
                    age = face["age"]
                    gender = '小姐姐' if face["gender"]['type'] == 'female' else '小哥哥'
                    beauty = face["beauty"]
                    beauty = round(math.sqrt(float(beauty)) * 10, 2)
                    location = face["location"]
                    left, top, width, height = tuple(
                        map(lambda x: int(location[x]), ('left', 'top', 'width', 'height')))
                    cv2.rectangle(ret_image, (left, top), (left + width, top + height), (0, 0, 255), 6)
                    reply += f'人脸概率为: {face_prob}, 这位{age}岁的{gender}颜值评分为{beauty}分/100分\n'
                tmp_img_path = 'tmp_img.png'
                cv2.imwrite(tmp_img_path, ret_image)
                itchat.send_image(tmp_img_path, to_user_name)
                itchat.send_msg(reply, to_user_name)
                if os.path.exists(tmp_img_path):
                    os.remove(tmp_img_path)
            else:
                itchat.send_msg(f'[什么也没识别到]\n {get_xiaobing_response("讲个笑话")}', to_user_name)
        else:
            itchat.send_msg(f'[什么也没识别到]\n {get_xiaobing_response("讲个笑话")}', to_user_name)
    else:
        itchat.send_msg(f'[什么也没识别到]\n {get_xiaobing_response("讲个笑话")}', to_user_name)


def generate_poem(content, to_user_name):
    print(content)
    if '藏头诗' in content:
        lines = content.split('\n')
        head, style = lines[1].replace('[头]', ''), lines[2].replace('[风格]', '')
        print(head, style)
        builder = subprocess.Popen(f'gen_poem.bat "{head}" "{style}" True')
        builder.wait()
        with open('tools/generate_poem/result.txt', 'r') as f:
            ret = f.readlines()[0]
            print(ret)
            itchat.send_msg(ret, to_user_name)


@itchat.msg_register([TEXT, PICTURE, RECORDING, ATTACHMENT, VIDEO, CARD, MAP, SHARING], isFriendChat=True)
def handle_friend_msg(msg):
    """
    # 好友信息监听
   :param msg:
   :return:
   """
    # print(json.dumps(msg, ensure_ascii=False))
    # print('朋友消息:\n')
    # pprint.pprint(msg)

    msg_id = msg['MsgId']  # 消息 id
    msg_from_name = msg['User']['NickName']  # 用户的昵称
    msg_from_name_remark = msg['User']['RemarkName']
    msg_from_uid = msg['FromUserName']  # 用户的昵称
    msg_to_uid = msg['ToUserName']

    msg_content = ''
    # 收到信息的时间
    msg_time_rec = time.time()
    msg_time_rec_format = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    msg_create_time = msg['CreateTime']
    msg_type = msg['Type']

    if msg_from_uid == msg_to_uid:
        global_vars['me_uid'] = msg_from_uid
        read_write_me_uid('w', content=global_vars['me_uid'])

    if msg_type == 'Text':
        if (options.is_gen_poem and
                (msg.get("User").get("NickName") in options.LISTENING_FRIENDS_NICKNAME or
                 msg.get("User").get("RemarkName") in options.LISTENING_FRIENDS_REMARK_NAME)):
            msg_content = msg['Content']
            print(msg_content)
            if '[藏头诗]' in msg_content and '[头]' in msg_content and '[风格]' in msg_content:
                if msg_from_uid == global_vars['me_uid']:
                    generate_poem(msg_content, msg_to_uid)
                else:
                    generate_poem(msg_content, msg_from_uid)

    if msg_type == 'Picture':
        if (options.is_enable_mark_face and
                (msg.get("User").get("NickName") in options.LISTENING_FRIENDS_NICKNAME or
                 msg.get("User").get("RemarkName") in options.LISTENING_FRIENDS_REMARK_NAME)):
            mark_face_dir = os.path.join(os.getcwd(), 'tmp', 'mark face')
            if not os.path.exists(mark_face_dir):
                os.makedirs(mark_face_dir)
            msg_content = os.path.join(mark_face_dir, msg['FileName'])
            msg['Text'](msg_content)  # 保存数据至此路径
            if msg_from_uid == global_vars['me_uid']:
                mark_face_baidu_api(msg_content, msg_to_uid)
            else:
                mark_face_baidu_api(msg_content, msg_from_uid)
            shutil.rmtree(mark_face_dir)
            # if os.path.exists(msg_content):
            #     os.remove(msg_content)

    # 不对自己的消息进行处理
    print(f'msg_from_uid: {msg_from_uid}, me: {global_vars["me_uid"]}')
    if msg_from_uid == global_vars['me_uid']:
        return

    if msg_type == 'Text':
        msg_content = msg['Content']
        print(f'{msg_time_rec_format}, '
              f'user:"{msg_from_name}", '
              f'remark name:"{msg_from_name_remark}", '
              f'content:"{msg_content}"')
        if (False and options.is_auto_reply and
                (msg.get("User").get("NickName") in options.LISTENING_FRIENDS_NICKNAME or
                 msg.get("User").get("RemarkName") in options.LISTENING_FRIENDS_REMARK_NAME)):
            return f'[自动回复]: {get_xiaobing_response(msg_content)}'

    elif msg_type in ('Picture', 'Recording', 'Video', 'Attachment'):
        msg_content = os.path.join(rec_tmp_dir, msg['FileName'])
        msg['Text'](msg_content)  # 保存数据至此路径

    # 名片，是无法用 itchat 发送的
    elif msg_type == 'Card':
        recommendInfo = msg['RecommendInfo']
        nickname = recommendInfo['NickName']
        sex = '男' if recommendInfo['Sex'] == 1 else '女'
        msg_content = '名片：{nickname},性别：{sex}'.format(nickname=nickname, sex=sex)

    # 地图与分享无法用 itchat 实现发送
    elif msg_type in ('Map', 'Sharing'):
        msg_content = msg['Url']

    rec_msg_dict.update({
        msg_id: {
            'is_group': False,
            'msg_from_name': msg_from_name,
            'msg_from_name_remark': msg_from_name_remark,
            'msg_from_uid': msg_from_uid,
            'msg_time_rec': msg_time_rec,
            'msg_create_time': msg_create_time,
            'msg_type': msg_type,
            'msg_content': msg_content
        }
    })


@itchat.msg_register([TEXT, PICTURE, RECORDING, ATTACHMENT, VIDEO, CARD, MAP, SHARING], isGroupChat=True)
def information(msg):
    """
    # 群聊信息监听
    :param msg:
    :return:
    """
    # print(json.dumps(msg, ensure_ascii=False))
    # print('群聊消息:\n')
    # pprint.pprint(msg)

    msg_id = msg['MsgId']  # 消息id
    msg_from_name = msg['ActualNickName']  # 发送者名称
    msg_from_uid = msg['ActualUserName']  # 发送者的id

    msg_group_uid = msg['User']['UserName']  # 群uid
    # import pprint
    # pprint.pprint(msg)

    msg_group_name = msg['User']['NickName']  # 群名称
    msg_self_display_name = msg['User']['Self']['DisplayName']

    msg_content = ''
    # 收到信息的时间
    msg_time_rec = time.time()
    msg_time_rec_format = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    msg_create_time = msg['CreateTime']
    msg_type = msg['Type']

    if (msg.get("User").get("NickName") in options.LISTENING_GROUPS and
            random.random() < 0.05):
        time.sleep(random.randint(3, 8))
        return msg['Content'].replace('王也', msg_from_name)

    if msg_type == 'Text':
        msg_content = msg['Content']
        print(f'{msg_time_rec_format}, '
              f'isAt:"{msg.get("isAt")}", '
              f'group:"{msg.get("User").get("NickName")}", '
              f'user:"{msg_from_name}", '
              f'content:"{msg["Content"]}"')

        if (options.is_gen_poem and
                (msg.get("User").get("NickName") in options.LISTENING_GROUPS)):
            if '[藏头诗]' in msg_content and '[头]' in msg_content and '[风格]' in msg_content:
                generate_poem(msg_content, msg_group_uid)

        if (options.is_auto_reply and msg.get("isAt") and
                (msg.get("User").get("NickName") in options.LISTENING_GROUPS)):
            return f'[自动回复]: {get_xiaobing_response(msg["Content"].strip(f"@{msg_self_display_name}").strip())}'

    elif msg_type in ('Picture', 'Recording', 'Video', 'Attachment'):
        msg_content = os.path.join(rec_tmp_dir, msg['FileName'])
        msg['Text'](msg_content)  # 保存数据至此路径

        if msg_type == 'Picture':
            if (options.is_enable_mark_face and
                    (msg.get("User").get("NickName") in options.LISTENING_GROUPS)):
                mark_face_baidu_api(msg_content, msg_group_uid)

    # 名片，是无法用 itchat 发送的
    elif msg_type == 'Card':
        recommendInfo = msg['RecommendInfo']
        nickname = recommendInfo['NickName']
        sex = '男' if recommendInfo['Sex'] == 1 else '女'
        msg_content = '名片：{nickname},性别：{sex}'.format(nickname=nickname, sex=sex)

    # 地图与分享无法用 itchat 实现发送
    elif msg_type in ('Map', 'Sharing'):
        msg_content = msg['Url']

    rec_msg_dict.update({
        msg_id: {
            'is_group': True,
            'msg_group_uid': msg_group_uid,
            'msg_group_name': msg_group_name,
            'msg_from_name': msg_from_name,
            'msg_from_uid': msg_from_uid,
            'msg_time_rec': msg_time_rec,
            'msg_create_time': msg_create_time,
            'msg_type': msg_type,
            'msg_content': msg_content
        }
    })
    # print(json.dumps(msg, ensure_ascii=False))


@itchat.msg_register([NOTE], isFriendChat=True, isGroupChat=True)
def revoke_msg(msg):
    """
    监听系统公告。
    :param msg:
    :return:
    """
    content = msg['Content']
    # print(json.dumps(msg, ensure_ascii=False))
    # pprint.pprint(msg)

    infos = re.findall(revoke_msg_compile, content, re.S)
    if infos:
        _, old_msg_id, nickname = infos[0]
        old_msg = rec_msg_dict.get(old_msg_id, {})
        if old_msg:
            # 判断文msg_content是否存在，不存在说明可能是
            msg_type = old_msg.get('msg_type')
            msg_content = old_msg.get('msg_content')
            msg_from_name = old_msg.get('msg_from_name')
            if not msg_type or not msg_content:
                return
            is_group = old_msg.get('is_group')
            send_msg = ''
            if is_group:
                if msg.get("User").get("NickName") not in options.LISTENING_GROUPS:
                    print(f'"{msg.get("User").get("NickName")}" --不在防撤回的群中')
                    return
                uid = old_msg.get('msg_group_uid')
                msg_type_name = content_type_dict.get(msg_type).get('name')  # 类型的中文名称
                send_msg = '群『{msg_group_name}』里的『{msg_from_name}』撤回了一条{msg_type_name}信息↓'.format(
                    msg_group_name=old_msg.get('msg_group_name'),
                    msg_from_name=msg_from_name,
                    msg_type_name=msg_type_name,
                )
            else:
                # 请勿在程序运行中取消对对象的备注，因为取消备注不会及时更新，而更换备注会及时更新
                # if (msg.get("User").get("NickName") not in options.LISTENING_FRIENDS_NICKNAME and
                #         msg.get("User").get("RemarkName") not in options.LISTENING_FRIENDS_REMARK_NAME):
                #     print(f'"{msg.get("User").get("NickName")}"或"{msg.get("User").get("RemarkName")}"'
                #           f' --不在防撤回的好友中')
                #     return
                uid = old_msg.get('msg_from_uid')
                msg_type_name = content_type_dict.get(msg_type).get('name')  # 类型的中文名称
                send_msg = '『{msg_from_name}』撤回了一条{msg_type_name}信息↓'.format(
                    msg_from_name=msg_from_name,
                    msg_type_name=msg_type_name,
                )
            # 私聊撤回发到filehelper中
            # uid = 'filehelper'
            send_revoke_msg(send_msg, uid, is_auto_forward=options.is_auto_forward)
            send_revoke_msg(msg_content, uid, msg_type, options.is_auto_forward)


def send_revoke_msg(msg_content, toUserName='filehelper', msg_type='Text', is_auto_forward=False):
    """
    :param msg_content: 消息内容
    :param toUserName: 用户uid
    :param msg_type: 消息类型
    :param is_auto_forward: 是否给用户发送撤回消息。
    :return:
    """
    # 消息类型不能为空，默认为文字消息
    if not msg_type or msg_type not in content_type_dict:
        msg_type = 'Text'
    #
    at_ = content_type_dict.get(msg_type).get('code')
    msg_content = '{}{}'.format(at_, msg_content)

    # 发送给文件传输助手
    if is_auto_forward and toUserName != 'filehelper':
        itchat.send(msg_content, toUserName)  # 发送给好友，或者群组。
    else:
        itchat.send(msg_content, 'filehelper')


def clear_cache():
    """
    # 每隔五分钟执行一次清理任务,如果有创建时间超过2分钟(120s)的记录，删除。
    # 非文本的话，连文件也删除
    :return:
    """
    cur_time = time.time()  # 当前时间
    for key, value in list(rec_msg_dict.items()):
        if cur_time - value.get('msg_time_rec') > 120:
            if value.get('msg_type') not in ('Text', 'Map', 'Card', 'Sharing'):
                file_path = value.get('msg_content')
                if os.path.exists(file_path):
                    os.remove(file_path)
            rec_msg_dict.pop(key)


def after_logout():
    """
    退出登录时，清理数据库，并关闭定时任务
    :return:
    """
    if scheduler and scheduler.get_jobs():
        scheduler.shutdown(wait=False)
    shutil.rmtree(rec_tmp_dir)


def before_login():
    """
    登录时，开启定时清理缓存
    :return:
    """

    itchat.get_friends(update=True)  # 更新用户好友状态
    itchat.get_chatrooms(update=True)  # 更新用户群组状态

    # 如果还存在定时任务，先关闭。
    if scheduler and scheduler.get_jobs():
        scheduler.shutdown(wait=False)
    scheduler.add_job(clear_cache, 'interval',
                      minutes=options.CLEAN_CACHE_INTERVAL_MINUTES,
                      misfire_grace_time=600)
    scheduler.start()


def read_write_me_uid(mode, me_uid_path='me.uid', **kwargs):
    if mode == 'r':
        with open(me_uid_path, 'r') as f:
            lines = f.readlines()
            if lines:
                return lines[0]
            else:
                return ''
    elif mode == 'w':
        with open(me_uid_path, 'w') as f:
            f.writelines(kwargs['content'])


if __name__ == '__main__':
    if os.path.exists(rec_tmp_dir):
        # 如果存在则删除文件，清理这些文件
        shutil.rmtree(rec_tmp_dir)
        # 创建缓存文件夹
        os.makedirs(rec_tmp_dir)
    else:
        # 创建缓存文件夹
        os.makedirs(rec_tmp_dir)

    global_vars['me_uid'] = read_write_me_uid('r')

    # itchat.logout()  # 如果微信在线，则退出。重新登录。
    itchat.auto_login(hotReload=True, loginCallback=before_login, exitCallback=after_logout)
    itchat.run(blockThread=True)
