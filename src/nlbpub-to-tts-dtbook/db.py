import copy
import datetime
import logging
import os
from decimal import Decimal

from mysql.connector import FieldType, errors, pooling

import cache
import server

"""
Database interface for MySQL/MariaDB database, which handles connecting
and re-connecting to the database.
"""
CONNECTION_POOL_SIZE = int(os.getenv("CONNECTION_POOL_SIZE", 25))

db_name = os.getenv("DB_NAME")
db_port = int(os.getenv("DB_PORT", default=3306))
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
db_host = os.getenv("DB_HOST")


class TestCursor():
    mock_responses = None

    current_response = None
    column_names = None
    description = None

    def __init__(self):
        self.mock_responses = []
        self.column_names = []
        self.description = []

    def execute(self, sql):
        if server.test:
            logging.info(sql)
            if len(self.mock_responses) == 0:
                assert False, "No more mock responses."
            else:
                self.current_response = self.mock_responses[0][0]
                self.column_names = self.mock_responses[0][1]
                self.description = self.mock_responses[0][2]

                self.mock_responses = self.mock_responses[1:]

    def fetchone(self):
        if len(self.current_response) == 0:
            return None

        result = self.current_response[0]
        self.current_response = self.current_response[1:]

        return copy.deepcopy(result)

    def fetchall(self):
        if len(self.current_response) == 0:
            return None

        result = self.current_response
        self.current_response = []

        return copy.deepcopy(result)

    def clean_mock_responses(self):
        self.mock_responses = []
        self.current_response = []
        self.column_names = []
        self.description = []
        cache.clean()

    def append_mock_response(self, response, column_names, description, response_number=None):
        response_position = None
        if response_number is not None:
            response_position = str(response_number + 1) + ("st" if response_number == 0 else "nd" if response_number == 1 else "th")

        if column_names is None and description is not None:
            column_names = tuple([d[0] for d in description])
        if column_names is not None and description is not None:
            filtered_description = []
            for column_name in column_names:
                for desc in description:
                    if desc[0] == column_name:
                        filtered_description.append(desc)
                        break
            description = filtered_description

        if description:
            for row_number, row in enumerate(response):
                row_position = str(row_number + 1) + ("st" if row_number == 0 else "nd" if row_number == 1 else "th")
                assert len(row) == len(description), (
                    f"invalid row length for {row_position} row in{' the ' + response_position if response_position else ''} mock response."
                    + f" Expected {len(description)}, was {len(row)}: {row}"
                )
                for col in range(len(description)):
                    if row[col] is None:
                        continue  # always allow None, regardless of column type

                    if description[col][1] == FieldType.TINY:
                        assert isinstance(row[col], bool) or row[col] in [0, 1], (
                            f"column {col} ({description[col][0]}) must be either a bool, or 0/1, was {type(row[col])}: {row[col]}"
                        )

                    elif description[col][1] in [FieldType.SHORT, FieldType.LONG, FieldType.LONGLONG, FieldType.INT24]:
                        assert isinstance(row[col], int), (
                            f"column {col} ({description[col][0]}) must be an integer, was {type(row[col])}: {row[col]}"
                        )

                    elif description[col][1] in [FieldType.DECIMAL, FieldType.FLOAT, FieldType.DOUBLE, FieldType.NEWDECIMAL]:
                        assert isinstance(row[col], float), (
                            f"column {col} ({description[col][0]}) must be a float, was {type(row[col])}: {row[col]}"
                        )

                    elif description[col][1] in [FieldType.STRING, FieldType.VARCHAR, FieldType.VAR_STRING, FieldType.VARCHAR,
                                                 FieldType.TINY_BLOB, FieldType.MEDIUM_BLOB, FieldType.LONG_BLOB, FieldType.BLOB]:
                        assert isinstance(row[col], str), (
                            f"column {col} ({description[col][0]}) must be a string, was {type(row[col])}: {row[col]}"
                        )

                    elif description[col][1] in [FieldType.DATE, FieldType.NEWDATE]:
                        assert isinstance(row[col], datetime.date), (
                            f"column {col} ({description[col][0]}) must be a date, was {type(row[col])}: {row[col]}"
                        )

                    elif description[col][1] in [FieldType.TIMESTAMP, FieldType.TIME]:
                        assert isinstance(row[col], datetime.timestamp), (
                            f"column {col} ({description[col][0]}) must be a timestamp, was {type(row[col])}: {row[col]}"
                        )

                    elif description[col][1] in [FieldType.DATETIME]:
                        assert isinstance(row[col], datetime.datetime), (
                            f"column {col} ({description[col][0]}) must be a datetime, was {type(row[col])}: {row[col]}"
                        )

                    else:
                        assert False, (
                            f"unknown column type ({description[col][1]}) for column {col} ({description[col][0]}) containing a {type(row[col])}: {row[col]}"
                        )

        self.mock_responses.append((response, column_names, description))


class TestConnection():
    _cursor = None

    def __init__(self):
        self._cursor = TestCursor()

    def is_connected(self):
        return True

    def cursor(self):
        return self._cursor

    def commit(self):
        return None


connection_pool = None
if server.test:
    connection_pool = TestConnection()

else:
    connection_pool = pooling.MySQLConnectionPool(pool_size=CONNECTION_POOL_SIZE,
                                                  pool_reset_session=True,
                                                  host=db_host,
                                                  port=db_port,
                                                  database=db_name,
                                                  user=db_user,
                                                  password=db_pass)


def with_cursor(func):
    global connection_pool

    def wrapper(*args, **kwargs):
        func_exception = None
        ret = ()

        # try getting a connection from the pool
        connection = None
        try:
            if server.test:
                connection = connection_pool
            else:
                connection = connection_pool.get_connection()
        except errors.PoolError:
            logging.exception("No database connections available")
            return {"head": {
                "message": "No database connections available."
            }, "data": None}, 500

        # invoke function
        try:
            ret = func(connection.cursor(), *args, **kwargs)
        except Exception as e:
            func_exception = e
        finally:
            if not server.test:
                try:
                    connection.close()
                except Exception:
                    logging.warn("Could not close database connection")

        # re-throw exception, if there was one
        if func_exception is not None:
            raise func_exception

        # return return value
        return ret

    return wrapper


def commit():
    """
    This method sends a COMMIT statement to the MySQL server, committing the current transaction.
    See: https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-commit.html
    """

    #  if connect():
    #      return connection.commit()
    #  TODO


PRINT_SQL_RESULT_DESCRIPTIONS = os.getenv("PRINT_SQL_RESULT_DESCRIPTIONS") in ["1", "true"]
last_sql_result_descriptions = None


def fetchone(cursor):
    global PRINT_SQL_RESULT_DESCRIPTIONS
    global last_sql_result_descriptions
    if PRINT_SQL_RESULT_DESCRIPTIONS:  # can be useful for debugging
        if cursor.description != last_sql_result_descriptions:
            logging.debug(cursor.description)
            last_sql_result_descriptions = cursor.description

    rows = fix_types(cursor.fetchone(), cursor)
    return rows


def fetchall(cursor):
    global PRINT_SQL_RESULT_DESCRIPTIONS
    global last_sql_result_descriptions
    if PRINT_SQL_RESULT_DESCRIPTIONS:  # can be useful for debugging
        if cursor.description != last_sql_result_descriptions:
            logging.debug(cursor.description)
            last_sql_result_descriptions = cursor.description

    rows = fix_types(cursor.fetchall(), cursor)
    return rows


def fix_types(row, cursor):
    if row is None:
        return row

    # row is a list of rows: iterate
    if type(row) == list:
        result = []
        for r in row:
            result.append(fix_types(r, cursor))
        return result

    else:
        result = []
        for i in range(len(row)):
            if cursor.description is not None and cursor.description[i][1] == FieldType.TINY:
                result.append(
                    row[i].lower() in ["true", "1"]
                    if isinstance(row[i], str)
                    else bool(row[i])
                )
            elif isinstance(row[i], Decimal):
                result.append(float(row[i]))
            else:
                result.append(row[i])
        return tuple(result)


def clean_mock_responses():
    if isinstance(connection_pool, TestConnection):
        connection_pool.cursor().clean_mock_responses()


def append_mock_response(response, column_names=None, description=None, response_number=None):
    if isinstance(connection_pool, TestConnection):
        connection_pool.cursor().append_mock_response(response, column_names=column_names, description=description, response_number=response_number)


def append_mock_responses(responses):
    for response_number, response_tuple in enumerate(responses):
        response = response_tuple[0]
        column_names = response_tuple[1] if len(response_tuple) > 1 else None
        description = response_tuple[2] if len(response_tuple) > 2 else None
        append_mock_response(response, column_names=column_names, description=description, response_number=response_number)
