from fabric.api import *
from fabric.contrib.console import confirm


@task
def build(flavor=None):
    server_name = prompt('Server name: ', default='NEWSERVER')
    if flavor == 'ember':
        postgres = False
        nginx = True
        memcached = False
        redis = False
        supervisor = False
    elif flavor == 'phoenix':
        postgres = True
        nginx = True
        memcached = True
        redis = False
        supervisor = False
    else:
        postgres = confirm("Install PostgreSQL?", default=False)
        nginx = confirm("Install NGINX?", default=False)
        memcached = confirm("Install Memcached?", default=False)
        redis = confirm("Install Redis?", default=False)
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
    run('useradd --system --shell=/bin/bash --home=/var/web --create-home web')
    sudo('ssh-keygen -t rsa -f /var/web/.ssh/id_rsa -C "web@%s" -q -N ""' % server_name, user='web', shell=False)
    put('~/.ssh/id_rsa.pub', '/var/web/.ssh/authorized_keys', mode=0644)
    run('chown web: /var/web/.ssh/authorized_keys')

    # NPM
    run('apt install npm -qy')

    if postgres:
        run('apt-get install postgresql-server-dev-9.3 postgresql-9.3 -qy')
        sudo('createuser -s web', user='postgres', shell=False)
        # Create backups user
        run('rm -rf /var/backups')
        run('useradd --system --shell=/bin/bash --home=/var/backups --create-home backups')
        sudo('ssh-keygen -t rsa -f /var/backups/.ssh/id_rsa -C "backups@%s" -q -N ""' % server_name, user='backups', shell=False)
        put('~/.ssh/id_rsa.pub', '/var/backups/.ssh/authorized_keys', mode=0644)
        sudo('cat /var/web/.ssh/id_rsa.pub >> /var/backups/.ssh/authorized_keys')
        run('chown backups: /var/backups/.ssh/authorized_keys')

    if nginx:
        run('apt-get install nginx -qy')
        put('./nginx.conf', '/etc/nginx/nginx.conf', mode=0644)
        put('./proxy_params', '/etc/nginx/proxy_params', mode=0644)

    if memcached:
        run('apt-get install memcached -qy')

    if redis:
        run('apt-get install redis-server -qy')

    if supervisor:
        run('apt-get install supervisor -qy')

    if flavor == 'ember':
        run('npm install -g fastboot-app-server')
        put('./ember-server.js', '/var/web/server.js', mode=0644)
        run('chown web: /var/web/server.js')

    print "\n\nADMIN PASSWORD\n\n%s\n\n" % admin_password
