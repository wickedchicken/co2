import plotly.express as px
import argparse
from datetime import datetime, timezone

from playhouse.mysql_ext import MariaDBConnectorDatabase

from co2 import get_config_data, get_db_connection_data, db_proxy, LogEntry

def get_args():
    parser = argparse.ArgumentParser()
    return parser.parse_args()


def plot(x, y):
    fig = px.bar(x=x, y=y)
    fig.write_html('data.html', auto_open=True)

def get_data(args):
    begin = datetime(2023, 7, 27, 00, 00, tzinfo=timezone.utc)
    # end = datetime(2023, 7, 27, 00, 00, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc)
    return LogEntry.select().where(LogEntry.recorded.between(begin, end)).order_by(LogEntry.recorded)

def main():
    config_data = get_config_data()
    db_login, db_password = get_db_connection_data(config_data)

    args = get_args()

    db = MariaDBConnectorDatabase(
        config_data['database']['name'],
        host=config_data['database']['hostname'],
        port=int(config_data['database']['port']),
        user=db_login,
        password=db_password,
    )
    db_proxy.initialize(db)
    db.connect()
    try:
        data = get_data(args)
        for row in data.tuples():
            print(row)
    finally:
        db.close()

if __name__ == '__main__':
    main()