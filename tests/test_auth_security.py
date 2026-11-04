import json
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.controllers.auth_controller import login, registrar_usuario
from app.database.database import Base
from app.models.carrito import Carrito
from app.models.categoria import Categoria
from app.models.compra import Compra
from app.models.intercambio import SolicitudIntercambio
from app.models.mensaje import Mensaje
from app.models.productos import Producto
from app.models.usuario import Usuario
from app.security.passwords import (
    hash_password,
    is_password_hash,
    migrate_legacy_passwords,
    verify_password,
)
from app.security.session import session_settings


class PasswordSecurityTests(unittest.TestCase):
    def test_hash_verifies_password_and_rejects_wrong_password(self):
        stored = hash_password("correct horse battery staple")

        self.assertTrue(is_password_hash(stored))
        self.assertTrue(verify_password("correct horse battery staple", stored))
        self.assertFalse(verify_password("incorrect password", stored))
        self.assertNotEqual(stored, "correct horse battery staple")

    def test_each_password_hash_uses_a_unique_salt(self):
        first = hash_password("a sufficiently long password")
        second = hash_password("a sufficiently long password")

        self.assertNotEqual(first, second)

    def test_legacy_password_migration_is_safe_and_idempotent(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        try:
            with session_factory() as db:
                db.add_all([
                    Usuario(
                        id=1, nombre="Legacy", email="legacy@example.test",
                        password="legacy-password", whatsapp="+573001234567",
                    ),
                    Usuario(
                        id=2, nombre="Hashed", email="hashed@example.test",
                        password=hash_password("already hashed password"),
                        whatsapp="+573001234568",
                    ),
                ])
                db.commit()

                self.assertEqual(migrate_legacy_passwords(db), 1)
                legacy_user = db.get(Usuario, 1)
                self.assertTrue(is_password_hash(legacy_user.password))
                self.assertTrue(verify_password("legacy-password", legacy_user.password))
                self.assertEqual(migrate_legacy_passwords(db), 0)
        finally:
            engine.dispose()

    def test_malformed_hash_is_rejected(self):
        self.assertFalse(verify_password("password", "scrypt$invalid"))


class SessionSettingsTests(unittest.TestCase):
    def test_development_uses_local_cookie_settings(self):
        settings = session_settings({"APP_ENV": "development"})

        self.assertFalse(settings["https_only"])
        self.assertEqual(settings["same_site"], "lax")
        self.assertEqual(settings["max_age"], 12 * 60 * 60)
        self.assertGreaterEqual(len(settings["secret_key"]), 32)

    def test_production_requires_a_strong_secret_and_https_cookies(self):
        with self.assertRaises(RuntimeError):
            session_settings({"APP_ENV": "production"})

        settings = session_settings({
            "APP_ENV": "production",
            "SESSION_SECRET": "a-production-secret-with-at-least-32-characters",
        })
        self.assertTrue(settings["https_only"])

    def test_short_secret_and_unknown_environment_are_rejected(self):
        with self.assertRaises(RuntimeError):
            session_settings({"APP_ENV": "development", "SESSION_SECRET": "too-short"})
        with self.assertRaises(RuntimeError):
            session_settings({"APP_ENV": "testing"})


class AuthenticationRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_registration_saves_a_hash_and_enforces_minimum_length(self):
        response = registrar_usuario(
            SimpleNamespace(),
            "Nuevo usuario",
            "NEW@example.test",
            "a secure password",
            "+573001234567",
            self.db,
        )
        self.assertEqual(response.status_code, 200)

        usuario = self.db.query(Usuario).filter_by(email="new@example.test").one()
        self.assertTrue(is_password_hash(usuario.password))
        self.assertTrue(verify_password("a secure password", usuario.password))

        rejected = registrar_usuario(
            SimpleNamespace(),
            "Otro usuario",
            "short@example.test",
            "short",
            "+573001234568",
            self.db,
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIsNone(self.db.query(Usuario).filter_by(email="short@example.test").first())

    def test_login_upgrades_legacy_password_and_creates_session(self):
        usuario = Usuario(
            nombre="Legacy", email="legacy@example.test", password="old password",
            whatsapp="+573001234567", rol="usuario", activo=True,
        )
        self.db.add(usuario)
        self.db.commit()
        request = SimpleNamespace(session={})

        response = login(request, "legacy@example.test", "old password", self.db)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(is_password_hash(usuario.password))
        self.assertEqual(request.session["usuario_id"], usuario.id)
        self.assertEqual(request.session["rol"], "usuario")
        self.assertTrue(json.loads(response.body)["ok"])


if __name__ == "__main__":
    unittest.main()
