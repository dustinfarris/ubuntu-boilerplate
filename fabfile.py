import base64
import crypt
import os
import random
import string

from fabric.api import *
from fabric.contrib.console import confirm


admin_password = ''


def generate_secret_key(length=64):
    return base64.b64encode(os.urandom(length))[:length]


def run_as(command, user):
    # This complicated wrapper allows us to run a command as a user as if the
    # user had logged in (getting all the .bashrc stuff, environment variables, etc)
    command = command.replace('$', '\\$').replace('"', '\\"')
    run('sudo -i -u {user} /bin/bash -lic "{command}"'.format(user=user, command=command), shell=False)


def do_basics(server_name):
    run('apt update -q')
    run('apt upgrade -qy')
    run('apt install tmux git-core vim unzip -qy')
    run('update-alternatives --set editor /usr/bin/vim.basic')

    put('./sudoers', '/etc/sudoers', mode=0440)

    run('locale-gen en_US.UTF-8')
    run('update-locale LANG=en_US.UTF-8')
    run('ln -sfn /usr/share/zoneinfo/America/New_York /etc/localtime')

    put('./bash.bashrc', '/etc/bash.bashrc', mode=0644)
    put('./root.bashrc', '/root/.bashrc', mode=0644)
    put('./skel.bashrc', '/etc/skel/.bashrc', mode=0644)
    run('touch /etc/skel/.hushlogin')

    put('./iptables', '/etc/network/iptables', mode=0644)
    put('./iptables-start', '/etc/network/if-pre-up.d/iptables', mode=0755)
    run('iptables-restore < /etc/network/iptables')

    put('./sshd_config', '/etc/ssh/sshd_config', mode=0644)

    run('hostname %s' % server_name)
    run('echo "%s" > /etc/hostname' % server_name)
    run('echo "127.0.1.1 %s" >> /etc/hosts' % server_name)

    # NPM
    run('apt install npm -qy')

    # Pip
    run('apt install python-setuptools python-dev build-essential -qy')
    run('easy_install pip')


def do_create_admin(server_name):

    global admin_password

    characters = string.letters + string.digits + '!@#$%^&*()-_=+~{[}],.<>?'
    password_size = 50
    # A possible 10,838,109,570,573,913,960,623,703,697,505,423,039,374,700,588,527,754,674,176
    # variations with this algorithm
    admin_password = ''.join((random.choice(characters) for x in range(password_size)))

    salt_characters = string.letters + string.digits
    salt = ''.join((random.choice(salt_characters) for x in range(3)))

    admin_crypt = crypt.crypt(admin_password, salt)

    run('useradd admin -Um -s /bin/bash -p %s' % admin_crypt)
    sudo('ssh-keygen -t rsa -f /home/admin/.ssh/id_rsa -C "admin@%s" -q -N ""' % server_name, user='admin', shell=False)
    put('~/.ssh/id_rsa.pub', '/home/admin/.ssh/authorized_keys', mode=0644)
    run('chown admin: /home/admin/.ssh/authorized_keys')

    return admin_password


def do_create_web_user(server_name):
    # Create web user
    run('useradd --system --shell=/bin/bash --home=/var/web --create-home web')
    sudo('ssh-keygen -t rsa -f /var/web/.ssh/id_rsa -C "web@%s" -q -N ""' % server_name, user='web', shell=False)
    put('~/.ssh/id_rsa.pub', '/var/web/.ssh/authorized_keys', mode=0644)
    run('chown web: /var/web/.ssh/authorized_keys')
    run_as('ssh-keygen -t rsa -f ~/ci_key -C "CI@{project}" -q -N ""'.format(project=project_name), user='web')
    run_as('cat ~/ci_key.pub >> ~/.ssh/authorized_keys', user='web')


def do_create_builder_user(server_name, project_name):
    # Create web user
    run('useradd --system --shell=/bin/bash --create-home builder')
    sudo('ssh-keygen -t rsa -f /home/builder/.ssh/id_rsa -C "builder@%s" -q -N ""' % server_name, user='builder', shell=False)
    put('~/.ssh/id_rsa.pub', '/home/builder/.ssh/authorized_keys', mode=0644)
    run('chown builder: /home/builder/.ssh/authorized_keys')
    run_as('ssh-keygen -t rsa -f ~/ci_key -C "CI@{project}" -q -N ""'.format(project=project_name), user='builder')
    run_as('cat ~/ci_key.pub >> ~/.ssh/authorized_keys', user='builder')


def do_install_postgres(server_name):
    run('apt install postgresql -qy')
    # Web db superuser
    sudo('createuser -s web', user='postgres', shell=False)
    # Create backups user
    run('rm -rf /var/backups')
    run('useradd --system --shell=/bin/bash --home=/var/backups --create-home backups')
    sudo('ssh-keygen -t rsa -f /var/backups/.ssh/id_rsa -C "backups@%s" -q -N ""' % server_name, user='backups', shell=False)
    put('~/.ssh/id_rsa.pub', '/var/backups/.ssh/authorized_keys', mode=0644)
    sudo('cat /var/web/.ssh/id_rsa.pub >> /var/backups/.ssh/authorized_keys')
    run('chown backups: /var/backups/.ssh/authorized_keys')


def do_letsencrypt(domain_name, email):
    run('openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048')
    run('git clone https://github.com/letsencrypt/letsencrypt /opt/letsencrypt')
    run('mkdir -p /var/web/letsencrypt')
    run('chgrp web /var/web/letsencrypt')
    run('mkdir -p /etc/letsencrypt/configs')
    put('./renew-letsencrypt.sh', '/usr/local/bin/renew-letsencrypt.sh')
    run('mkdir -p /var/log/letsencrypt')
    run("sed -i 's/DOMAIN_NAME/{domain}/g' /usr/local/bin/renew-letsencrypt.sh".format(domain=domain_name))
    run('chmod 755 /usr/local/bin/renew-letsencrypt.sh')
    run('(crontab -l; echo "0 0 1 JAN,MAR,MAY,JUL,SEP,NOV * /usr/local/bin/renew-letsencrypt.sh") | crontab')
    run("sed -i 's/DOMAIN_NAME/{domain}/g' /etc/nginx/sites-available/{domain}.conf".format(domain=domain_name))
    sudo('ln -sfn /etc/nginx/sites-available/{domain}.conf /etc/nginx/sites-enabled/{domain}.conf'.format(domain=domain_name))
    run('service nginx restart')
    put('./letsencrypt', '/etc/letsencrypt/configs/{domain}.conf'.format(domain=domain_name))
    run("sed -i 's/DOMAIN_NAME/{domain}/g' /etc/letsencrypt/configs/{domain}.conf".format(domain=domain_name))
    run("sed -i 's/USER_EMAIL/{email}/g' /etc/letsencrypt/configs/{domain}.conf".format(email=email, domain=domain_name))
    run('/opt/letsencrypt/letsencrypt-auto --config /etc/letsencrypt/configs/{domain}.conf certonly'.format(domain=domain_name))
    run("sed -i 's/# ssl_cert/ssl_cert/g' /etc/nginx/sites-available/{domain}.conf".format(domain=domain_name))
    run('service nginx restart')


def do_install_nginx(domain_name):
    run('apt install nginx -qy')
    run("sed -i 's/www-data/web/g' /etc/nginx/nginx.conf")
    put('./nginx-proxy-params', '/etc/nginx/proxy_params', mode=0644)
    put('./nginx-ssl-params', '/etc/nginx/ssl_params', mode=0644)


def do_install_memcached():
    run('apt install memcached -qy')


def do_install_redis():
    run('apt install redis-server -qy')


def do_install_supervisor():
    run('apt install supervisor -qy')


def do_install_erlang_elixir(erlang_version, elixir_version, user):
    # Erlang requirements
    run('apt install libncurses5-dev -qy')
    # We will use asdf package manager for erlang and elixir
    # Note that this will compile erlang and elixir which can take a while
    run_as('git clone https://github.com/asdf-vm/asdf.git ~/.asdf', user=user)
    # These have to go in .profile because automators may not use bash
    run_as("echo '. $HOME/.asdf/asdf.sh' >> ~/.profile", user=user)
    run_as("echo '. $HOME/.asdf/completions/asdf.bash' >> ~/.profile", user=user)
    # Install erlang and elixir
    run_as("asdf plugin-add erlang https://github.com/asdf-vm/asdf-erlang.git", user=user)
    run_as("asdf plugin-add elixir https://github.com/asdf-vm/asdf-elixir.git", user=user)
    run_as("asdf install erlang {version}".format(version=erlang_version), user=user)
    run_as("asdf global erlang {version}".format(version=erlang_version), user=user)
    run_as("asdf install elixir {version}".format(version=elixir_version), user=user)
    run_as("asdf global elixir {version}".format(version=elixir_version), user=user)
    # A couple necessities
    run_as("mix local.hex --force", user=user)
    run_as("mix local.rebar --force", user=user)


def do_configure_aws(aws_access_key_id, aws_secret_access_key):
    run('pip install awscli')
    run('mkdir -p /var/web/.aws')
    put('./aws-config', '/var/web/.aws/config')
    put('./aws-credentials', '/var/web/.aws/credentials')
    run("sed -i 's/AWS_ACCESS_KEY_ID/{key}/g' /var/web/.aws/credentials".format(key=aws_access_key_id.replace('/', '\/')))
    run("sed -i 's/AWS_SECRET_ACCESS_KEY/{key}/g' /var/web/.aws/credentials".format(key=aws_secret_access_key.replace('/', '\/')))
    run('chown -R web: /var/web/.aws')


def do_configure_fastboot(s3_bucket, s3_key):
    put('./fastboot-server.js', '/var/web/server.js', mode=0644)
    run('chown web: /var/web/server.js')
    run("sed -i 's/S3_BUCKET/%s/g' /var/web/server.js" % s3_bucket)
    run("sed -i 's/S3_KEY/%s/g' /var/web/server.js" % s3_key)


def do_ember(project_name):
    production = confirm("Production server?", default=True)
    server_name = prompt(
      'Server name: ',
      default='%s-web' % project_name if production else 'stage-%s-web' % project_name
    )
    domain_name = prompt(
      'Domain name: ',
      default='%s.com' % project_name if production else 'stage.%s.com' % project_name
    )
    email = prompt('Email (for letsencrypt): ', default='admin@%s.com' % project_name)
    s3_bucket = prompt('S3 Bucket: ', default='%s-deploy' % server_name)
    s3_key = prompt('S3 Key: ', default=project_name)
    aws_access_key_id = prompt('AWS Access Key ID: ')
    aws_secret_access_key = prompt('AWS Secret Access Key: ')
    do_basics(server_name)
    do_create_admin(server_name)
    do_create_web_user(server_name)
    do_install_nginx(domain_name)
    do_install_supervisor()
    do_configure_aws(aws_access_key_id, aws_secret_access_key)
    do_configure_fastboot(s3_bucket, s3_key)
    put('./fastboot-nginx.conf', '/etc/nginx/sites-available/%s.conf' % domain_name, mode=0644)
    do_letsencrypt(domain_name, email)
    put('./fastboot-supervisor', '/etc/supervisor/conf.d/fastboot.conf', mode=0644)
    run_as('npm install fastboot-app-server fastboot-s3-downloader fastboot-s3-notifier', user='web')
    run('service supervisor restart')
    print "\n\nYour Ember server is ready.\n\n"


def do_phoenix(project_name):
    production = confirm("Production server?", default=True)
    server_name = prompt(
      'Server name: ',
      default='%s-app' % project_name if production else 'stage-%s-app' % project_name
    )
    domain_name = prompt(
      'Domain name: ',
      default='app.%s.com' % project_name if production else 'stage.app.%s.com' % project_name
    )
    email = prompt('Email (for letsencrypt): ', default='admin@%s.com' % project_name)
    do_basics(server_name)
    do_create_admin(server_name)
    do_create_web_user(server_name)
    do_install_postgres(server_name)
    do_install_nginx(domain_name)
    put('./phoenix-nginx.conf', '/etc/nginx/sites-available/%s.conf' % domain_name, mode=0644)
    do_letsencrypt(domain_name, email)
    print "\n\nYour Phoenix server is ready.\n\n"


def put_phoenix_secret_config(environment, project_name, db_user, db_pass):
    run_as('mkdir -p ~/_config', user='builder')
    secret_path = '/home/builder/_config/{env}.secret.exs'.format(env=environment)
    put('./secret.exs', secret_path, mode=0644)
    secret_key = generate_secret_key().replace('/', '\\/')
    run("sed -i 's/SECRET_KEY/{secret_key}/g' {path}".format(secret_key=secret_key, path=secret_path))
    run("sed -i 's/Example/{project}/g' {path}".format(project=project_name.capitalize(), path=secret_path))
    run("sed -i 's/example/{project}/g' {path}".format(project=project_name, path=secret_path))
    run("sed -i 's/DB_USER/{db_user}/g' {path}".format(db_user=db_user, path=secret_path))
    run("sed -i 's/DB_PASS/{db_pass}/g' {path}".format(db_pass=db_pass, path=secret_path))
    run('chown -R builder: /home/builder/_config')


def setup_build_scripts(github_path):
    # Nevermind this is a bad idea for now
    project_name = github_path.split('/')[-1]
    put('./build.sh', '/home/builder/build', mode=0755)
    run('chown builder: /home/builder/build')
    path = github_path.replace('/', '\\/')
    run("sed -i 's/GITHUB_PATH/{path}/g' /home/builder/build".format(path=path))
    run("sed -i 's/PROJECT_NAME/{name}/g' /home/builder/build".format(name=project_name))
    run_as('mkdir -p ~/_source', user='builder')


def do_build(project_name):
    # github_path = prompt('GitHub path: ', default='dustinfarris/%s' % project_name)
    server_name = prompt('Server name: ', default='%s-build' % project_name)
    erlang_version = prompt('Erlang version: ', default='18.3')
    elixir_version = prompt('Elixir version: ', default='1.2.6')
    prod_db_user = prompt('DB username (prod): ', default='web')
    prod_db_pass = prompt('DB password (prod): ', default=generate_secret_key(20))
    stage_db_user = prompt('DB username (stage): ', default='web')
    stage_db_pass = prompt('DB password (stage): ', default=generate_secret_key(20))
    do_basics(server_name)
    do_create_admin(server_name)
    do_create_builder_user(server_name, project_name)

    do_install_erlang_elixir(erlang_version, elixir_version, user='builder')

    put_phoenix_secret_config('prod', project_name, prod_db_user, prod_db_pass)
    put_phoenix_secret_config('stage', project_name, stage_db_user, stage_db_pass)

    print "\n\nYour build server is almost ready.  Remember to:\n\n"
    print "\t- Update config in /home/builder/_config/*.secret.exs\n"


@task
def build(flavor=None):
    project_name = prompt('Project name: ')
    try:
        if flavor == 'ember':
            do_ember(project_name)
        elif flavor == 'phoenix':
            do_phoenix(project_name)
        elif flavor == 'build':
            do_build(project_name)
    except:
        print "\n\nSomething went wrong, see traceback.\n\n"
        raise
    else:
        print "\n\nEnjoy!\n\n"
    finally:
        if admin_password:
            print "\n\nADMIN PASSWORD\n\n%s\n\n" % admin_password
