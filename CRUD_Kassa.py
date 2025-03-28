import xmlrpc.client
import logging
import traceback

class OdooUserManager:
    def __init__(self, url: str, db: str, username: str, password: str):
        """
        Initialize Odoo connection and authentication
        
        :param url: Odoo server URL
        :param db: Database name
        :param username: Username for authentication
        :param password: Password or API key
        """
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        
        # Configure logging with console and file output
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('odoo_user_deletion.log'),
                logging.StreamHandler()  # Add console output
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Authenticate and establish connection
        self.common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        
        # Detailed authentication debugging
        self._debug_authentication()

    def _debug_authentication(self):
        """
        Provide detailed debugging for authentication
        """
        try:
            self.logger.debug(f"Attempting authentication:")
            self.logger.debug(f"URL: {self.url}")
            self.logger.debug(f"Database: {self.db}")
            self.logger.debug(f"Username: {self.username}")
            
            # Test connection to common endpoint
            server_info = self.common.version()
            self.logger.debug(f"Server Version Info: {server_info}")
            
            # Attempt authentication
            self.uid = self.common.authenticate(self.db, self.username, self.password, {})
            
            if not self.uid:
                self.logger.error("Authentication failed: Invalid credentials or configuration")
                raise ValueError("Authentication failed: Invalid credentials")
            
            self.logger.info(f"Successfully authenticated with UID: {self.uid}")
        
        except xmlrpc.client.Fault as fault:
            self.logger.error(f"XML-RPC Fault: {fault.faultCode} - {fault.faultString}")
            raise
        except Exception as e:
            self.logger.error(f"Detailed Authentication Error: {e}")
            self.logger.error(traceback.format_exc())
            raise

    def list_databases(self):
        """
        List available databases (debug method)
        """
        try:
            databases = self.common.list()
            self.logger.info(f"Available Databases: {databases}")
            return databases
        except Exception as e:
            self.logger.error(f"Error listing databases: {e}")
            return []

def main():
    # Configuration - Detailed debugging setup
    URL = "http://localhost:8069"  # Odoo server URL
    
    # Try multiple potential database and username combinations
    database_attempts = ['odoo', 'postgres']
    username_attempts = ['admin', 'odoo']
    password_attempts = ['admin', 'odoo']

    for db in database_attempts:
        for username in username_attempts:
            for password in password_attempts:
                try:
                    print(f"\nTrying: DB={db}, Username={username}, Password={password}")
                    
                    # Initialize Odoo User Manager
                    user_manager = OdooUserManager(URL, db, username, password)
                    
                    # List available databases as an additional check
                    user_manager.list_databases()
                    
                    # If successful, you can proceed with further actions
                    print("Successfully connected!")
                    return
                
                except Exception as e:
                    print(f"Connection attempt failed: {e}")
                    continue

if __name__ == "__main__":
    main()