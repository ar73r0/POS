import configparser

def read_database_config(config_path="odoo/config/odoo.conf"):
    config = configparser.ConfigParser()
    config.read(config_path)

    return {
        "dbname": config.get("options", "db_name"),
        "user": config.get("options", "db_user"),
        "password": config.get("options", "db_password"),
        "host": config.get("options", "db_host"),
        "port": config.get("options", "db_port")
    }
