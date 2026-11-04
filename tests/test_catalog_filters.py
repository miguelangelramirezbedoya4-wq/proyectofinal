import unittest
from types import SimpleNamespace


class CatalogFilterTests(unittest.TestCase):
    def test_excludes_current_user_products_from_purchase_options(self):
        producto_propio = SimpleNamespace(vendedor_id=7, disponible=True)
        producto_ajeno = SimpleNamespace(vendedor_id=9, disponible=True)

        from app.controllers.usuario_controller import _filtrar_productos_para_compra

        self.assertFalse(_filtrar_productos_para_compra(producto_propio, 7))
        self.assertTrue(_filtrar_productos_para_compra(producto_ajeno, 7))


if __name__ == "__main__":
    unittest.main()
