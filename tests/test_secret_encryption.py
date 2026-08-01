import unittest

from src.application.secrets import CredentialService
from src.application.workspaces import bootstrap_platform
from src.infrastructure.crypto import SecretCipher, SecretDecryptionError
from src.infrastructure.models import ProviderCredentialModel, WorkspaceModel
from tests.platform_helpers import platform_fixture


class SecretEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.database, self.passwords, self.cipher, _ = platform_fixture()
        self.service = CredentialService(self.cipher)
        with self.database.session() as session:
            self.user, self.workspace = bootstrap_platform(
                session,
                email="admin@example.test",
                password="correct horse battery staple",
                display_name="Admin",
                workspace_slug="first-workspace",
                workspace_name="First",
                hard_limit="10",
                passwords=self.passwords,
            )

    def tearDown(self):
        self.database.engine.dispose()

    def test_api_status_never_returns_secret_and_ciphertext_is_authenticated(self):
        with self.database.session() as session:
            status = self.service.put(
                session,
                workspace_id=self.workspace.id,
                actor_user_id=self.user.id,
                provider="OpenRouter",
                value="very-secret-value",
            )
            self.assertFalse(hasattr(status, "value"))
            record = session.query(ProviderCredentialModel).one()
            self.assertNotIn("very-secret-value", record.ciphertext)
            record.ciphertext = record.ciphertext[:-1] + ("A" if record.ciphertext[-1] != "A" else "B")
        with self.database.session() as session:
            with self.assertRaises(SecretDecryptionError):
                self.service.resolve(
                    session, workspace_id=self.workspace.id, provider="openrouter"
                )

    def test_workspace_is_bound_as_associated_data(self):
        with self.database.session() as session:
            self.service.put(
                session,
                workspace_id=self.workspace.id,
                actor_user_id=self.user.id,
                provider="google",
                value="secret",
            )
            other = WorkspaceModel(slug="other-workspace", name="Other")
            session.add(other)
            session.flush()
            record = session.query(ProviderCredentialModel).one()
            with self.assertRaises(SecretDecryptionError):
                self.cipher.decrypt(
                    record.ciphertext,
                    associated_data=f"provider:{other.id}:google:v1",
                )


if __name__ == "__main__":
    unittest.main()
