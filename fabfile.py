from fabric.api import *
from fabric.contrib.console import confirm


@task
def build():
    postgres = confirm("Install PostgreSQL?", default=False)
    nginx = confirm("Install NGINX?", default=False)
    redis = confirm("Install Redis?", default=False)
    rabbitmq = confirm("Install RabbitMQ?", default=False)
    supervisor = confirm("Install Supervisor?", default=False)

    run('apt-get update -q')
    run('apt-get upgrade -qy')
    run('apt-get install git-core vim -qy')
    run('update-alternatives --set editor /usr/bin/vim.basic')

    put('./sudoers', '/etc/sudoers', mode=440)

    run('locale-gen en_US.UTF-8')
    run('update-locale LANG=en_US.UTF-8')
    run('ln -sfn /usr/share/zoneinfo/America/New_York /etc/localtime')

    put('./bash.bashrc', '/etc/bash.bashrc', mode=644)
    put('./root.bashrc', '/root/.bashrc', mode=644)
    put('./skel.bashrc', '/etc/skel/.bashrc', mode=644)

    put('./iptables', '/etc/network/iptables', mode=644)
    put('./iptables-start', '/etc/network/if-pre-up.d/iptables', mode=755)
    run('iptables-save > iptables-restore')

    # Python 3.x stuff
    run('apt-get install build-essential gcc python3-dev python3-setuptools bash-completion htop ipython3 -qy')
    run('easy_install3 pip')
    run('pip install ipdb virtualenv')
    run('apt-get install git-core mercurial subversion -qy')
    run('apt-get install python3-imaging -qy')

    if postgres:
        run('apt-get install postgresql-server-dev-9.1 postgresql-9.1 -qy')

    if nginx:
        run('apt-get install nginx -qy')

    if redis:
        run('apt-get install redis-server -qy')

    if rabbitmq:
        run('apt-get install rabbitmq-server -qy')

    if supervisor:
        run('apt-get install supervisor -qy')
