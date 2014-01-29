# Ubuntu Boilerplate

This is a [fabfile][] script designed to get the bare-necessities ready for server
deployment.  It is tailored for use with newly spun up Rackspace instances, but should
work with any Ubuntu server.

## Prerequisites

You will need Fabric to run this script.

```console
pip install Fabric
```

## Usage

Simply run the script.  It will perform boilerplate installs and prompt you for a couple
extras like PostgreSQL and Memcached (default is No for all extras).

```console
fab -H root@<host> build
```

## Example

```console
fab -H root@192.293.48.10 build
```

or, to build multiple servers at the same time

```console
fab -H root@192.111.11.11,root@192.222.22.22,root@192.333.33.33 build
```


[fabfile]: http://docs.fabfile.org/en/latest/
