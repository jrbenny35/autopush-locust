from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function
import base64
import os
from contextlib import closing
from typing import final
from urllib.parse import urlparse, urljoin

import json
import uuid
import time
import gevent

import requests
from websocket import create_connection
from websocket._exceptions import WebSocketTimeoutException
import six

from locust import HttpUser, TaskSet, task, between

class ConnectionTaskSet(TaskSet):
    # def on_start(self):
    #     self.user_id = ...
    #     ws = create_connection("wss://autopush.dev.mozaws.net:443", header={"Origin": "http://localhost:1337"}, ssl=False)
    #     self.ws = ws

    @task
    def test_basic(self):
        encrypted_data = "aLongStringOfEncryptedThings"
        headers = {"TTL": "60", "Content-Encoding": "aes128gcm"}
        channel_id = str(uuid.uuid4())
        ws = create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False)
      
        body = json.dumps(dict(messageType="hello", use_webpush=True))
        ws.send(body)
        res = json.loads(ws.recv())
        assert res["messageType"] == "hello"
        body = json.dumps(dict(messageType="register", channelID=channel_id))
        ws.send(body)
        res = json.loads(ws.recv())
        if os.getenv("AUTOPUSH_RUST_SERVER") and (os.getenv("AUTOPUSH_ENV") != "dev"):
            path = urlparse(res["pushEndpoint"]).path
            endpoint_url = urljoin("https://endpoint-autopush.stage.mozaws.net/", path) # URLS["rs_server_url"]
        else:
            endpoint_url = res["pushEndpoint"]
        start_time = time.time()
        endpoint_res = self.client.post(
            url=endpoint_url,
            name="Push Endpoint URL",
            data=base64.urlsafe_b64decode(encrypted_data),
            headers=headers,
        )
        assert endpoint_res.status_code == 201, f"status code was {endpoint_res.status_code}"
        res = json.loads(ws.recv())
        assert res["data"] == encrypted_data
        end_time = time.time()
        print(end_time)
        ws.send(json.dumps(dict(messageType="ack", updates=dict(channelID=channel_id))))
        ws.close()

        self.user.environment.events.request.fire(
            request_type="WSS",
            name="WSS Endpoint URL",
            response_time=int((end_time - start_time) * 1000),
            response_length=len(res),
            exception=None,
            context=None,
        )

    @task
    def test_basic_topic(self):
        topic_one = "aaaa"
        encrypted_data = ["aLongStringOfEncryptedThings", "aDiffferentStringFullOfStuff"]
        headers = {"TTL": "60", "Content-Encoding": "aes128gcm", "Topic": topic_one}
        channel_id = str(uuid.uuid4())
        ws = create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False)

        body = json.dumps(dict(messageType="hello", use_webpush=True))
        ws.send(body)
        res = json.loads(ws.recv())
        assert res["messageType"] == "hello"
        uaid = res["uaid"]
        body = json.dumps(dict(messageType="register", channelID=channel_id))
        ws.send(body)
        res = json.loads(ws.recv())
        ws.close()
        
        if os.getenv("AUTOPUSH_RUST_SERVER") and (os.getenv("AUTOPUSH_ENV") != "dev"):
            path = urlparse(res["pushEndpoint"]).path
            endpoint_url = urljoin("https://endpoint-autopush.stage.mozaws.net/", path) # URLS["rs_server_url"]
        else:
            endpoint_url = res["pushEndpoint"]
        endpoint_res = self.client.post(
            url=endpoint_url,
            name="Push Endpoint URL",
            data=base64.urlsafe_b64decode(encrypted_data[0]),
            headers=headers,
        )
        assert endpoint_res.status_code == 201, f"status code was {endpoint_res.status_code}"
        endpoint_res = self.client.post(
            url=endpoint_url,
            name="Push Endpoint URL",
            data=base64.urlsafe_b64decode(encrypted_data[1]),
            headers=headers,
        )
        assert endpoint_res.status_code == 201, f"status code was {endpoint_res.status_code}"

        # connect and check notification
        with closing(
            create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False, timeout=60)) as ws:
                start_time = time.time()
                body = json.dumps(dict(messageType="hello", use_webpush=True, uaid=uaid))
                ws.send(body)
                res = json.loads(ws.recv())
                assert res["messageType"] == "hello"
                msg = json.loads(ws.recv())
                assert msg["data"] == encrypted_data[1]
                end_time = time.time()
                ws.send(json.dumps(dict(messageType="ack", updates=dict(channelID=channel_id))))
        self.user.environment.events.request.fire(
            request_type="WSS",
            name="WSS Endpoint URL",
            response_time=int((end_time - start_time) * 1000),
            response_length=len(res),
            exception=None,
            context=None,
        )   

    @task
    def test_connect_and_hold(self):
        with closing(create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False)) as ws:
            start_time = time.time()
            body = json.dumps(dict(messageType="hello", use_webpush=True))
            ws.send(body)
            res = json.loads(ws.recv())
            assert res["messageType"] == "hello"
            end_time = time.time()
            self.user.environment.events.request.fire(
                request_type="WSS",
                name=f"test_connect_and_hold",
                response_time=int((end_time - start_time) * 1000),
                response_length=len(res),
                exception=None,
                context=None
            )
            time.sleep(30)

    @task
    def test_connect(self):
        with closing(create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False)) as ws:
            start_time = time.time()
            body = json.dumps(dict(messageType="hello", use_webpush=True))
            ws.send(body)
            res = json.loads(ws.recv())
            assert res["messageType"] == "hello"
            end_time = time.time()
            self.user.environment.events.request.fire(
                request_type="WSS",
                name=f"test_connect",
                response_time=int((end_time - start_time) * 1000),
                response_length=len(res),
                exception=None,
                context=None
            )

    @task
    def test_connect_stored(self):
        topic_one = "aaaa"
        encrypted_data = "aLongStringOfEncryptedThings"
        headers = {"TTL": "60", "Content-Encoding": "aes128gcm", "Topic": topic_one}
        channel_id = str(uuid.uuid4())
        ws = create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False)

        body = json.dumps(dict(messageType="hello", use_webpush=True))
        ws.send(body)
        res = json.loads(ws.recv())
        assert res["messageType"] == "hello"
        uaid = res["uaid"]
        body = json.dumps(dict(messageType="register", channelID=channel_id))
        ws.send(body)
        res = json.loads(ws.recv())
        ws.close()
        
        if os.getenv("AUTOPUSH_RUST_SERVER") and (os.getenv("AUTOPUSH_ENV") != "dev"):
            path = urlparse(res["pushEndpoint"]).path
            endpoint_url = urljoin("https://endpoint-autopush.stage.mozaws.net/", path) # URLS["rs_server_url"]
        else:
            endpoint_url = res["pushEndpoint"]
        for _ in range(10):
          endpoint_res = self.client.post(
              url=endpoint_url,
              name="Push Endpoint URL",
              data=base64.urlsafe_b64decode(encrypted_data),
              headers=headers,
          )
          assert endpoint_res.status_code == 201, f"status code was {endpoint_res.status_code}"
        ws.close()

        # connect and check notification
        msg_count = 0
        exception = None
        for _ in range(10):
            try:
                ws = create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False, timeout=30)
                start_time = time.time()
                body = json.dumps(dict(messageType="hello", use_webpush=True, uaid=uaid))
                ws.send(body)
                res = json.loads(ws.recv())
                assert res["messageType"] == "hello"
                msg = json.loads(ws.recv())
                assert msg["data"]
                msg_count += 1
                end_time = time.time()
                ws.send(json.dumps(dict(messageType="ack", updates=dict(channelID=channel_id))))
                ws.close()
            except WebSocketTimeoutException as e:
                end_time = time.time()
                exception = e
            finally:
                self.user.environment.events.request.fire(
                    request_type="WSS",
                    name=f"test_connect_stored",
                    response_time=int((end_time - start_time) * 1000),
                    response_length=len(res),
                    exception=exception,
                    context=None
                )
                ws.close()
        assert msg_count == 10

    # @task
    def test_connect_forever(self):
        topic_one = "aaaa"
        encrypted_data = "aLongStringOfEncryptedThings"
        headers = {"TTL": "60", "Content-Encoding": "aes128gcm", "Topic": topic_one}
        channel_id = str(uuid.uuid4())
        ws = create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False)

        body = json.dumps(dict(messageType="hello", use_webpush=True))
        ws.send(body)
        res = json.loads(ws.recv())
        assert res["messageType"] == "hello"
        uaid = res["uaid"]
        body = json.dumps(dict(messageType="register", channelID=channel_id))
        ws.send(body)
        res = json.loads(ws.recv())
        if os.getenv("AUTOPUSH_RUST_SERVER") and (os.getenv("AUTOPUSH_ENV") != "dev"):
            path = urlparse(res["pushEndpoint"]).path
            endpoint_url = urljoin("https://endpoint-autopush.stage.mozaws.net/", path) # URLS["rs_server_url"]
        else:
            endpoint_url = res["pushEndpoint"]
        while True:
            endpoint_res = self.client.post(
                url=endpoint_url,
                name="Push Endpoint URL",
                data=base64.urlsafe_b64decode(encrypted_data),
                headers=headers,
            )
            assert endpoint_res.status_code == 201, f"status code was {endpoint_res.status_code}"
            ws.close()
            time.sleep(15)
            ws = create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False)
            body = json.dumps(dict(messageType="hello", use_webpush=True, uaid=uaid))
            ws.send(body)
            res = json.loads(ws.recv())
            assert res["messageType"] == "hello"
            ws.recv()
            ws.send(json.dumps(dict(messageType="ack", updates=dict(channelID=channel_id))))
            ws.close()

    # @task
    # def test_notification_forever_unsubscribed(self):
    #     encrypted_data = "aLongStringOfEncryptedThings"
    #     headers = {"TTL": "60", "Content-Encoding": "aes128gcm"}
    #     channel_id = str(uuid.uuid4())
    #     with closing(create_connection("wss://autopush.stage.mozaws.net", header={"Origin": "http://localhost:1337"}, ssl=False)) as ws:
    #         body = json.dumps(dict(messageType="hello", use_webpush=True))
    #         ws.send(body)
    #         res = json.loads(ws.recv())
    #         assert res["messageType"] == "hello"
    #         body = json.dumps(dict(messageType="register", channelID=channel_id))
    #         ws.send(body)
    #         res = json.loads(ws.recv())
    #         endpoint_url = res["pushEndpoint"]
    #         body = json.dumps(dict(messageType="unregister", channelID=channel_id))
    #         ws.send(body)
    #         while True:
    #             ws.ping("hello")
    #             with self.client.post(
    #                 url=endpoint_url,
    #                 name="Push Endpoint URL",
    #                 data=base64.urlsafe_b64decode(encrypted_data),
    #                 headers=headers,
    #                 catch_response=True
    #             ) as response:
    #                 if response.status_code == 410:
    #                     response.success()
    #             try:
    #                 ws.recv()
    #             except BrokenPipeError:
    #                 continue
    #             ws.send(json.dumps(dict(messageType="ack")))
    #             time.sleep(30)

        

class LocustRunner(HttpUser):
    tasks = [ConnectionTaskSet]
    host = "https://updates-autopush.stage.mozaws.net"
    # wait_time = between(1, 5)
