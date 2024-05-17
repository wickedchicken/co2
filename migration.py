from playhouse.migrate import *

from playhouse.mysql_ext import MariaDBConnectorDatabase

from co2 import get_config_data, get_db_connection_data, db_proxy, LogEntry




measurement_type = CharField(index=True, default='sensor_recording')

config_data = get_config_data()
db_login, db_password = get_db_connection_data(config_data)
db = MariaDBConnectorDatabase(
    config_data['database']['name'],
    host=config_data['database']['hostname'],
    port=int(config_data['database']['port']),
    user=db_login,
    password=db_password,
)
migrator = MySQLMigrator(db)
with db.transaction():
    migrate(
        migrator.add_column('logentry', 'measurement_type', measurement_type),
    )