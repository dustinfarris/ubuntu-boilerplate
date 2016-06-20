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
        supervisor = True
        domain_name = prompt('Domain name: ', default='example.com')
        s3_bucket = prompt('S3 Bucket: ')
        s3_key = prompt('S3 Key: ')
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
    run('echo "%s %s" >> /etc/hosts' % (env.host_string.split('@')[-1], server_name))

    # Create admin user
    import string
    import random
    import crypt

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

    # Create web user
    run('useradd --system --shell=/bin/bash --home=/var/web --create-home web')
    sudo('ssh-keygen -t rsa -f /var/web/.ssh/id_rsa -C "web@%s" -q -N ""' % server_name, user='web', shell=False)
    put('~/.ssh/id_rsa.pub', '/var/web/.ssh/authorized_keys', mode=0644)
    run('chown web: /var/web/.ssh/authorized_keys')

    # NPM
    run('apt install npm -qy')

    # Pip
    run('apt install python-setuptools python-dev build-essential -qy')
    run('easy_install pip')

    try:
        if postgres:
            run('apt install postgresql-server-dev-9.3 postgresql-9.3 -qy')
            sudo('createuser -s web', user='postgres', shell=False)
            # Create backups user
            run('rm -rf /var/backups')
            run('useradd --system --shell=/bin/bash --home=/var/backups --create-home backups')
            sudo('ssh-keygen -t rsa -f /var/backups/.ssh/id_rsa -C "backups@%s" -q -N ""' % server_name, user='backups', shell=False)
            put('~/.ssh/id_rsa.pub', '/var/backups/.ssh/authorized_keys', mode=0644)
            sudo('cat /var/web/.ssh/id_rsa.pub >> /var/backups/.ssh/authorized_keys')
            run('chown backups: /var/backups/.ssh/authorized_keys')

        if nginx:
            run('apt install nginx -qy')
            run("sed -i 's/www-data/web/g' /etc/nginx/nginx.conf")
            put('./nginx-proxy-params', '/etc/nginx/proxy_params', mode=0644)
            put('./nginx-ssl-params', '/etc/nginx/ssl_params', mode=0644)
            run('openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048')
            run('git clone https://github.com/letsencrypt/letsencrypt /opt/letsencrypt')

        if memcached:
            run('apt install memcached -qy')

        if redis:
            run('apt install redis-server -qy')

        if supervisor:
            run('apt install supervisor -qy')

        if flavor == 'ember':
            run('pip install awscli')
            put('./fastboot-server.js', '/var/web/server.js', mode=0644)
            run('chown web: /var/web/server.js')
            run("sed -i 's/S3_BUCKET/%s/g' /var/web/server.js" % s3_bucket)
            run("sed -i 's/S3_KEY/%s/g' /var/web/server.js" % s3_key)
            put('./fastboot-nginx.conf', '/etc/nginx/sites-available/%s.conf' % domain_name, mode=0644)
            run("sed -i 's/DOMAIN_NAME/{domain}/g' /etc/nginx/sites-available/{domain}.conf".format(domain=domain_name))
            sudo('ln -sfn /etc/nginx/sites-available/{domain}.conf /etc/nginx/sites-enabled/{domain}.conf'.format(domain=domain_name))
            put('./fastboot-supervisor', '/etc/supervisor/conf.d/fastboot.conf', mode=0644)
            run('service nginx reload')
            print "\n\nYour Ember server is almost ready, be sure to:\n\n"
            print "\tRun letsencrypt\n"
            print "\tAdd letsencrypt to crontab\n"
            print "\tUncomment SSL lines in Nginx config\n"
            print "\tInstall fastboot and dependencies as web user\n"
            print "\tUpdate AWS credentials using `aws configure`"
            print "\tRestart nginx and supervisor\n"
    finally:
        print "\n\nDone!\n\n"
        print "\n\nADMIN PASSWORD\n\n%s\n\n" % admin_password
