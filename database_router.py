class AppDatabaseRouter:
    def db_for_read(self, model, **hints):
        """Send Product queries to the products_db and everything else to default."""
        if model._meta.app_label == 'product':
            return 'product_db'  # Use the correct database
        return 'default'

    def db_for_write(self, model, **hints):
        """Write Product data to the products_db."""
        if model._meta.app_label == 'product':
            return 'product_db'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations only between objects in the same database."""
        if obj1._state.db == obj2._state.db:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure migrations only happen in the correct database."""
        if app_label == 'product':
            return db == 'product_db'  # Product app should only migrate to products_db
        return db == 'default'  # Everything else should use the default DB
