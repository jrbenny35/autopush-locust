from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function
import base64
from contextlib import closing
from urllib.parse import urlparse, urljoin

import json
import uuid
import time

from websocket import create_connection
from websocket._exceptions import WebSocketTimeoutException

from locust import HttpUser, TaskSet, task, events


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument(
        "--websocket_url",
        type=str,
        env_var="AUTOPUSH_WEBSOCKET_URL",
        default="",
        help="Server URL",
    )
    parser.add_argument(
        "--endpoint_url",
        type=str,
        env_var="AUTOPUSH_ENDPOINT_URL",
        default="",
        help="Endpoint URL",
    )


class ConnectionTaskSet(TaskSet):
    @task
    def test_basic(self):

        encrypted_data = "aLongStringOfEncryptedThings"
        headers = {"TTL": "60", "Content-Encoding": "aes128gcm"}
        channel_id = str(uuid.uuid4())
        ws = create_connection(
            self.user.environment.parsed_options.websocket_url,
            header={"Origin": "http://localhost:1337"},
            ssl=False,
        )

        body = json.dumps(dict(messageType="hello", use_webpush=True))
        ws.send(body)
        res = json.loads(ws.recv())
        assert res["messageType"] == "hello"
        body = json.dumps(dict(messageType="register", channelID=channel_id))
        ws.send(body)
        res = json.loads(ws.recv())
        if self.user.environment.parsed_options.endpoint_url and (
            "dev" not in self.user.environment.parsed_options.websocket_url
        ):
            path = urlparse(res["pushEndpoint"]).path
            endpoint_url = urljoin(
                self.user.environment.parsed_options.endpoint_url, path
            )
        else:
            endpoint_url = res["pushEndpoint"]
        start_time = time.time()
        endpoint_res = self.client.post(
            url=endpoint_url,
            name="ENDPOINT test_basic",
            data=base64.urlsafe_b64decode(encrypted_data),
            headers=headers,
        )
        assert (
            endpoint_res.status_code == 201
        ), f"status code was {endpoint_res.status_code}"
        res = json.loads(ws.recv())
        assert res["data"] == encrypted_data
        end_time = time.time()
        ws.send(json.dumps(dict(messageType="ack", updates=dict(channelID=channel_id))))
        ws.close()

        self.user.environment.events.request.fire(
            request_type="WSS",
            name="WEBSOCKET test_basic",
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
        ws = create_connection(
            self.user.environment.parsed_options.websocket_url,
            header={"Origin": "http://localhost:1337"},
            ssl=False,
        )

        body = json.dumps(dict(messageType="hello", use_webpush=True))
        ws.send(body)
        res = json.loads(ws.recv())
        assert res["messageType"] == "hello"
        uaid = res["uaid"]
        body = json.dumps(dict(messageType="register", channelID=channel_id))
        ws.send(body)
        res = json.loads(ws.recv())
        ws.close()

        if self.user.environment.parsed_options.endpoint_url and (
            "dev" not in self.user.environment.parsed_options.websocket_url
        ):
            path = urlparse(res["pushEndpoint"]).path
            endpoint_url = urljoin(
                self.user.environment.parsed_options.endpoint_url, path
            )
        else:
            endpoint_url = res["pushEndpoint"]
        endpoint_res = self.client.post(
            url=endpoint_url,
            name="ENDPOINT test_basic_topic",
            data=base64.urlsafe_b64decode(encrypted_data[0]),
            headers=headers,
        )
        assert (
            endpoint_res.status_code == 201
        ), f"status code was {endpoint_res.status_code}"
        endpoint_res = self.client.post(
            url=endpoint_url,
            name="ENDPOINT test_basic_topic",
            data=base64.urlsafe_b64decode(encrypted_data[1]),
            headers=headers,
        )
        assert (
            endpoint_res.status_code == 201
        ), f"status code was {endpoint_res.status_code}"

        # connect and check notification
        with closing(
            create_connection(
                self.user.environment.parsed_options.websocket_url,
                header={"Origin": "http://localhost:1337"},
                ssl=False,
                timeout=60,
            )
        ) as ws:
            start_time = time.time()
            body = json.dumps(dict(messageType="hello", use_webpush=True, uaid=uaid))
            ws.send(body)
            res = json.loads(ws.recv())
            assert res["messageType"] == "hello"
            msg = json.loads(ws.recv())
            assert msg["data"] == encrypted_data[1]
            end_time = time.time()
            ws.send(
                json.dumps(dict(messageType="ack", updates=dict(channelID=channel_id)))
            )
        self.user.environment.events.request.fire(
            request_type="WSS",
            name="WEBSOCKET test_basic_topic",
            response_time=int((end_time - start_time) * 1000),
            response_length=len(res),
            exception=None,
            context=None,
        )

    @task
    def test_connect_and_hold(self):
        with closing(
            create_connection(
                self.user.environment.parsed_options.websocket_url,
                header={"Origin": "http://localhost:1337"},
                ssl=False,
            )
        ) as ws:
            start_time = time.time()
            body = json.dumps(dict(messageType="hello", use_webpush=True))
            ws.send(body)
            res = json.loads(ws.recv())
            assert res["messageType"] == "hello"
            end_time = time.time()
            self.user.environment.events.request.fire(
                request_type="WSS",
                name="WEBSOCKET test_connect_and_hold",
                response_time=int((end_time - start_time) * 1000),
                response_length=len(res),
                exception=None,
                context=None,
            )
            time.sleep(30)

    @task
    def test_connect(self):
        with closing(
            create_connection(
                self.user.environment.parsed_options.websocket_url,
                header={"Origin": "http://localhost:1337"},
                ssl=False,
            )
        ) as ws:
            start_time = time.time()
            body = json.dumps(dict(messageType="hello", use_webpush=True))
            ws.send(body)
            res = json.loads(ws.recv())
            assert res["messageType"] == "hello"
            end_time = time.time()
            self.user.environment.events.request.fire(
                request_type="WSS",
                name="WEBSOCKET test_connect",
                response_time=int((end_time - start_time) * 1000),
                response_length=len(res),
                exception=None,
                context=None,
            )

    @task
    def test_connect_stored(self):
        topic_one = "aaaa"
        encrypted_data = "aLongStringOfEncryptedThings"
        headers = {"TTL": "60", "Content-Encoding": "aes128gcm", "Topic": topic_one}
        channel_id = str(uuid.uuid4())
        ws = create_connection(
            self.user.environment.parsed_options.websocket_url,
            header={"Origin": "http://localhost:1337"},
            ssl=False,
        )

        body = json.dumps(dict(messageType="hello", use_webpush=True))
        ws.send(body)
        res = json.loads(ws.recv())
        assert res["messageType"] == "hello"
        uaid = res["uaid"]
        body = json.dumps(dict(messageType="register", channelID=channel_id))
        ws.send(body)
        res = json.loads(ws.recv())
        ws.close()

        if self.user.environment.parsed_options.endpoint_url and (
            "dev" not in self.user.environment.parsed_options.websocket_url
        ):
            path = urlparse(res["pushEndpoint"]).path
            endpoint_url = urljoin(
                self.user.environment.parsed_options.endpoint_url, path
            )
        else:
            endpoint_url = res["pushEndpoint"]
        for _ in range(10):
            endpoint_res = self.client.post(
                url=endpoint_url,
                name="ENDPOINT test_connect_stored",
                data=base64.urlsafe_b64decode(encrypted_data),
                headers=headers,
            )
            assert (
                endpoint_res.status_code == 201
            ), f"status code was {endpoint_res.status_code}"
        ws.close()

        # connect and check notification
        msg_count = 0
        exception = None
        for _ in range(10):
            try:
                ws = create_connection(
                    self.user.environment.parsed_options.websocket_url,
                    header={"Origin": "http://localhost:1337"},
                    ssl=False,
                    timeout=30,
                )
                start_time = time.time()
                body = json.dumps(dict(messageType="hello", use_webpush=True, uaid=uaid))
                ws.send(body)
                res = json.loads(ws.recv())
                assert res["messageType"] == "hello"
                msg = json.loads(ws.recv())
                assert msg["data"]
                msg_count += 1
                end_time = time.time()
                ws.send(
                    json.dumps(
                        dict(messageType="ack", updates=dict(channelID=channel_id))
                    )
                )
                ws.close()
            except WebSocketTimeoutException as e:
                end_time = time.time()
                exception = e
            finally:
                self.user.environment.events.request.fire(
                    request_type="WSS",
                    name=f"WEBSOCKET test_connect_stored",
                    response_time=int((end_time - start_time) * 1000),
                    response_length=len(res),
                    exception=exception,
                    context=None,
                )
                ws.close()
        assert msg_count == 10

    @task
    def test_connect_forever(self):
        topic_one = "aaaa"
        encrypted_data = "aLongStringOfEncryptedThings"
        headers = {"TTL": "60", "Content-Encoding": "aes128gcm", "Topic": topic_one}
        channel_id = str(uuid.uuid4())
        ws = create_connection(
            self.user.environment.parsed_options.websocket_url,
            header={"Origin": "http://localhost:1337"},
            ssl=False,
        )

        body = json.dumps(dict(messageType="hello", use_webpush=True))
        ws.send(body)
        res = json.loads(ws.recv())
        assert res["messageType"] == "hello"
        uaid = res["uaid"]
        body = json.dumps(dict(messageType="register", channelID=channel_id))
        ws.send(body)
        res = json.loads(ws.recv())
        if self.user.environment.parsed_options.endpoint_url and (
            "dev" not in self.user.environment.parsed_options.websocket_url
        ):
            path = urlparse(res["pushEndpoint"]).path
            endpoint_url = urljoin(
                self.user.environment.parsed_options.endpoint_url, path
            )
        else:
            endpoint_url = res["pushEndpoint"]
        while True:
            endpoint_res = self.client.post(
                url=endpoint_url,
                name="ENDPOINT test_connect_forever",
                data=base64.urlsafe_b64decode(encrypted_data),
                headers=headers,
            )
            assert (
                endpoint_res.status_code == 201
            ), f"status code was {endpoint_res.status_code}"
            ws.close()
            time.sleep(15)
            ws = create_connection(
                self.user.environment.parsed_options.websocket_url,
                header={"Origin": "http://localhost:1337"},
                ssl=False,
            )
            body = json.dumps(dict(messageType="hello", use_webpush=True, uaid=uaid))
            ws.send(body)
            res = json.loads(ws.recv())
            assert res["messageType"] == "hello"
            ws.recv()
            ws.send(
                json.dumps(dict(messageType="ack", updates=dict(channelID=channel_id)))
            )

            ws.close()

    @task
    def test_notification_forever_unsubscribed(self):
        encrypted_data = "aLongStringOfEncryptedThings"
        headers = {"TTL": "60", "Content-Encoding": "aes128gcm"}
        channel_id = str(uuid.uuid4())
        with closing(
            create_connection(
                self.user.environment.parsed_options.websocket_url,
                header={"Origin": "http://localhost:1337"},
                ssl=False,
            )
        ) as ws:
            body = json.dumps(dict(messageType="hello", use_webpush=True))
            ws.send(body)
            res = json.loads(ws.recv())
            assert res["messageType"] == "hello"
            body = json.dumps(dict(messageType="register", channelID=channel_id))
            ws.send(body)
            res = json.loads(ws.recv())
            endpoint_url = res["pushEndpoint"]
            body = json.dumps(dict(messageType="unregister", channelID=channel_id))
            ws.send(body)
            while True:
                ws.ping("hello")
                with self.client.post(
                    url=endpoint_url,
                    name="ENDPOINT test_notification_forever_unsubscribed",
                    data=base64.urlsafe_b64decode(encrypted_data),
                    headers=headers,
                    catch_response=True,
                ) as response:
                    if response.status_code == 410:
                        response.success()
                try:
                    ws.recv()
                except BrokenPipeError:
                    continue
                ws.send(json.dumps(dict(messageType="ack")))
                time.sleep(30)


class LocustRunner(HttpUser):
    tasks = [ConnectionTaskSet]
    host = "https://updates-autopush.stage.mozaws.net"
