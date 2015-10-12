from fabric.api import *
from fabric.contrib.console import confirm


@task
def celery():
    put('./celerybeat.default', '/etc/default/celerybeat', mode=0644, use_sudo=True)
    put('./celeryd.default', '/etc/default/celeryd', mode=0644, use_sudo=True)
    put('./celerybeat.initd', '/etc/init.d/celerybeat', mode=0755, use_sudo=True)
    put('./celeryd.initd', '/etc/init.d/celeryd', mode=0755, use_sudo=True)
    run('mkdir -p /var/run/celery')


@task
def build(flavor=None):
    server_name = prompt('Server name: ', default='NEWSERVER')
    if flavor == 'app':
        postgres = True
        nginx = True
        memcached = True
        redis = True
        rabbitmq = True
        supervisor = True
    elif flavor == 'db':
        postgres = True
        nginx = False
        memcached = False
        redis = True
        rabbitmq = False
        supervisor = False
    elif flavor == 'web':
        postgres = False
        nginx = True
        memcached = False
        redis = False
        rabbitmq = False
        supervisor = False
    elif flavor == 'cms':
        postgres = True
        nginx = True
        memcached = True
        redis = True
        rabbitmq = True
        supervisor = True
    else:
        postgres = confirm("Install PostgreSQL?", default=False)
        nginx = confirm("Install NGINX?", default=False)
        memcached = confirm("Install Memcached?", default=False)
        redis = confirm("Install Redis?", default=False)
        rabbitmq = confirm("Install RabbitMQ?", default=False)
        supervisor = confirm("Install Supervisor?", default=False)

    run('apt-get update -q')
    run('apt-get upgrade -qy')
    run('apt-get install tmux git-core vim -qy')
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
    run('echo "%s %s" >> /etc/hosts' % (env.host_string.split('@')[-1], server_name))

    # Create admin user
    import string
    import random
    import crypt

    characters = string.letters + string.digits + '!@#$%^&*()-_=+~{[}],.<>?'
    password_size = 30
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

    # Create web user
    run('useradd --system --shell=/bin/bash --home=/var/www --create-home web')
    sudo('ssh-keygen -t rsa -f /var/www/.ssh/id_rsa -C "web@%s" -q -N ""' % server_name, user='web', shell=False)
    sudo('echo "alias activate=\'source env/bin/activate\'" > /var/www/.bash_aliases', user='web', shell=False)
    put('~/.ssh/id_rsa.pub', '/var/www/.ssh/authorized_keys', mode=0644)
    run('chown web: /var/www/.ssh/authorized_keys')
    run('chown web: /var/www/.bash_aliases')

    # Create backups user
    run('rm -rf /var/backups')
    run('useradd --system --shell=/bin/bash --home=/var/backups --create-home backups')
    sudo('ssh-keygen -t rsa -f /var/backups/.ssh/id_rsa -C "backups@%s" -q -N ""' % server_name, user='backups', shell=False)
    put('~/.ssh/id_rsa.pub', '/var/backups/.ssh/authorized_keys', mode=0644)
    sudo('cat /var/www/.ssh/id_rsa.pub >> /var/backups/.ssh/authorized_keys')
    run('chown backups: /var/backups/.ssh/authorized_keys')

    # Celery (configs only)
    put('./celerybeat.default', '/etc/default/celerybeat', mode=0644)
    put('./celeryd.default', '/etc/default/celeryd', mode=0644)
    put('./celerybeat.initd', '/etc/init.d/celerybeat', mode=0755)
    put('./celeryd.initd', '/etc/init.d/celeryd', mode=0755)
    run('mkdir -p /var/run/celery')
    run('chown web: /var/run/celery')

    # NodeJS
    run('apt-get install python-software-properties python g++ make -qy')
    run('add-apt-repository ppa:chris-lea/node.js -y')
    run('apt-get update -q')
    run('apt-get install nodejs -qy')

    # Python 3.x stuff
    run('apt-get install build-essential gcc python3-dev python3-setuptools bash-completion htop libjpeg-dev ipython3 -qy')
    run('easy_install3 pip')
    run('pip install ipdb virtualenv')
    run('apt-get install git-core mercurial subversion -qy')
    run('apt-get install python3-imaging libpq-dev -qy')

    # uWSGI
    run('apt-get install libpcre3 libpcre3-dev -qy')
    run('pip install uwsgi')
    run('mkdir -p /etc/uwsgi/vassals')
    put('./uwsgi.conf', '/etc/init/uwsgi.conf', mode=0644)
    run('mkdir -p /var/log/uwsgi')
    run('chown web: /var/log/uwsgi')

    if postgres:
        run('apt-get install postgresql-server-dev-9.3 postgresql-9.3 -qy')
        sudo('createuser -s web', user='postgres', shell=False)

    if nginx:
        run('apt-get install nginx -qy')
        put('./nginx.conf', '/etc/nginx/nginx.conf', mode=0644)
        put('./proxy_params', '/etc/nginx/proxy_params', mode=0644)

    if memcached:
        run('apt-get install memcached -qy')

    if redis:
        run('apt-get install redis-server -qy')

    if rabbitmq:
        run('apt-get install rabbitmq-server -qy')

    if supervisor:
        run('apt-get install supervisor -qy')

    print "\n\nADMIN PASSWORD\n\n%s\n\n" % admin_password
