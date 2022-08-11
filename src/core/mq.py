#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

#------------------------------------------------------------------------------
# Message Queue (RabbitMQ)
#------------------------------------------------------------------------------
class MQ():
    """
    This class implements a message queue (RabbitMQ).
    """

    def __init__(self, mq_host, mq_port, mq_user, mq_pass, mq_vhost):
        """
        Initializes the message queue.
        """
        super().__init__()
        self.mq_host = mq_host
        self.mq_port = mq_port
        self.mq_user = mq_user
        self.mq_pass = mq_pass
        self.mq_vhost = mq_vhost
        self.mq_connection = None
        self.mq_channel = None
        self.mq_exchange = None
        self.mq_routing_key = None

    def connect(self):
        """
        Connects to the message queue.
        """
        from pika import PlainCredentials, BlockingConnection, ConnectionParameters

        self.mq_connection = BlockingConnection(ConnectionParameters(self.mq_host, self.mq_port, self.mq_vhost, credentials=PlainCredentials(self.mq_user, self.mq_pass)))
        self.mq_channel = self.mq_connection.channel()
        self.mq_channel.confirm_delivery()
        self.mq_channel.exchange_declare(exchange=self.mq_exchange, exchange_type='topic')

    def publish(self, exchange, routing_key, message):
        """
        Publishes a message to the message queue.
        """
        from pika import BasicProperties, exceptions as pika_exceptions

        try:
            self.mq_channel.basic_publish(exchange=exchange, routing_key=routing_key, body=message, properties=BasicProperties(delivery_mode=2))
        except pika_exceptions.ConnectionClosed:
            self.connect()
            self.mq_channel.basic_publish(exchange=exchange, routing_key=routing_key, body=message, properties=BasicProperties(delivery_mode=2))
        except pika_exceptions.ChannelClosed:
            self.connect()
            self.mq_channel.basic_publish(exchange=exchange, routing_key=routing_key, body=message, properties=BasicProperties(delivery_mode=2))
        except pika_exceptions.ChannelError:
            logging.info(f'MQ: Channel error while publishing message to exchange {exchange} with routing key {routing_key}.')

    def subscribe(self, exchange, routing_key, callback):
        """
        Subscribes to a message queue.
        """
        self.mq_exchange = exchange
        self.mq_routing_key = routing_key

        self.mq_channel.exchange_declare(exchange=exchange, exchange_type='topic')
        self.mq_channel.queue_declare(queue=routing_key)
        self.mq_channel.queue_bind(queue=routing_key, exchange=exchange, routing_key=routing_key)
        self.mq_channel.basic_consume(callback, queue=routing_key, no_ack=False)
        self.mq_channel.start_consuming()

    def close(self):
        """
        Closes the message queue.
        """
        self.mq_channel.close()
        self.mq_connection.close()

    def __del__(self):
        """
        Destructor.
        """
        self.close()        
