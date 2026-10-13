"""IPv4 SMTP sockets must retain the encryption required by port 465."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import app as web


class SmtpTlsTests(unittest.TestCase):
    def test_ssl_returns_encrypted_socket_with_server_hostname(self):
        smtp = object.__new__(web._IPv4SMTP_SSL)
        smtp.context = Mock()
        raw = Mock()
        encrypted = smtp.context.wrap_socket.return_value
        with patch.object(web, '_smtp_connect_ipv4', return_value=raw):
            result = smtp._get_socket('smtp.qq.com', 465, 20)
        self.assertIs(result, encrypted)
        smtp.context.wrap_socket.assert_called_once_with(raw, server_hostname='smtp.qq.com')

    def test_tls_failure_closes_raw_socket(self):
        smtp = object.__new__(web._IPv4SMTP_SSL)
        smtp.context = Mock()
        smtp.context.wrap_socket.side_effect = OSError('TLS handshake failed')
        raw = Mock()
        with patch.object(web, '_smtp_connect_ipv4', return_value=raw):
            with self.assertRaises(OSError):
                smtp._get_socket('smtp.qq.com', 465, 20)
        raw.close.assert_called_once()

    def test_starttls_keeps_initial_socket_plain(self):
        smtp = object.__new__(web._IPv4SMTP)
        raw = Mock()
        with patch.object(web, '_smtp_connect_ipv4', return_value=raw):
            self.assertIs(smtp._get_socket('smtp.qq.com', 587, 20), raw)


if __name__ == '__main__':
    unittest.main()
