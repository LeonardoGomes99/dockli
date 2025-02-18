import paramiko
import configparser

config = configparser.ConfigParser()
config.read("config_file.ini")

SSH_HOST = config.get("SSH", "host", fallback=None)
SSH_PORT = config.getint("SSH", "port", fallback=22)
SSH_USER = config.get("SSH", "user", fallback=None)
SSH_PASSWORD = config.get("SSH", "password", fallback=None)
SSH_KEY_FILE = config.get("SSH", "key_file", fallback=None)

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if SSH_KEY_FILE:
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, key_filename=SSH_KEY_FILE)
    else:
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD)

    print("✅ Conexão bem-sucedida!")
    ssh.close()

except paramiko.AuthenticationException:
    print("❌ Erro de autenticação: usuário/senha ou chave SSH incorretos.")

except paramiko.SSHException as e:
    print(f"❌ Erro no SSH: {e}")

except Exception as e:
    print(f"❌ Outro erro: {e}")
