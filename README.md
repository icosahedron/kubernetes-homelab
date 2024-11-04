# Set up a Web Server in a Kubernetes Cluster in Docker with NFS Shares

# A Homelab

Setting up a homelab is a great way to learn about technologies.

This homelab is set up using [KinD](https://kind.sigs.k8s.io/), 
the Kubernetes in Docker version of K8s, on an Ubuntu 24.04 VM in Hyper-V. 
All nodes will be on the same VM in docker containers.

I put this on Github for permanence reasons, but also so people 
could learn from it perhaps. File issues with problems or improvements
as fitting.

## Tools

A number of tools are required to install the cluster. I've used [Homebrew](https://brew.sh) to manage these.

* [just](https://just.systems/) - convenient command runner with needing separate scripts
* docker - container management (see below)
* [kind](https://kind.sigs.k8s.io/) - K8s cluster in Docker containers
* [helm](https://helm.sh/) - application template
* [kapp](https://carvel.dev/kapp/) - application installer (use this instead of helm because of resource watching)

## Install Docker for Containers

Docker is required for this configuration, so install it if it's not available. 
See the [official Docker documentation](https://docs.docker.com/engine/install/ubuntu) 
for instructions on installing Docker.

## Create the cluster

To bring up the cluster, use the just command line runner.

```
just create-cluster
```

This will bring up the cluster with a control plane and two workers (as defined
at the time of this writing) with nothing else installed.

The config file used is `yaml/config.kind.yaml`.

## Cluster Storage

Storage for the cluster is handled by an in-cluster NFS server. The NFS server
is mapped to the `storage` subdirectory in the cloned repo. Installing the apps will
create the necessary directories under the storage directory.

Each PV for the applications so far has been set to 'retain', so configuration
changes and redeployments of applications below shouldn't erase any data.

The storage should be installed when an application is installed, but by itself
can be installed with `just install-nfs-server`.

(Instructions inspired by [CSI Driver NFS Example](https://github.com/kubernetes-csi/csi-driver-nfs/blob/master/deploy/example/nfs-provisioner/README.md)).

## Install Applications

There are currently 3 applications that can be deployed: Nginx (2 instances), Postgres, and Gitea.

Installing each app will install its dependencies (e.g. Gitea relies on Postgres).

Uninstalling each app will remove the kubernetes resources, but not the files/storage
for each one. Feel free to reconfigure and redeploy each app as desired.

### Nginx

Install with `just deploy-nginx`. Uninstall with `just delete-nginx`.

This is a simple installation that will serve whatever is in the `storage/nginx` directory.
A default "Hello, world" index.html file is in this directory. Just put whatever files you want here and they should be served.

Additional hosts/sites can be configured with ingress resources.

### Postgres

Install with `just deploy-postgres`. Uninstall with `just delete-postgres`.

This is a vanilla installation with the admin account 'homelab' and password 'homelab'.

There is no LoadBalancer or NodePort configured for it, so a port-forward needs 
to be used to connect to the database from outside the cluster.

In cluster the service name is `postgres-postgresql.db.svc.cluster.local` and port is 5432.

### Gitea

Install with `just deploy-gitea`. Uninstall with `just delete-gitea`.

An empty instance of Gitea is installed. It includes an init job that will initialize 
the Postgres database, but the installation set up still has to be done.

The assumption is to use the in-cluster Postgres database, which is initialized with
the appropriate roles and database created. The name is gitea/gitea. 

This is not mandatory. You can use the SQLite database if you wish.

The ingress is configured to forward host `gitea.icosahedron.dev` to port 3000
to the gitea pod.

## Test the cluster

Now it's time to test the configuration of the cluster.

Let's install a web server and see if it can read a file off the NFS share. Look in the `yaml` directory for files to deploy an nginx web server configured to read files off the NFS share.

Put a test `index.html` file in `./storage/nginx`. Save the following (or whatever you want) to that path.

```
<html>
<head><title>NGINX in Kind</title></head>
<body>
<center><h1>NGINX in Kind</h1></center>
<hr><center>nginx</center>
</body>
</html>
```

Use the command `curl http://localhost` to see if the web server works, and it should return the contents of the file that we put in the directory.

If this is what you see, congratulations, you have set up Kubernetes cluster with NFS storage.

## TODO

- [ ] More applications
- [ ] Deployment on separate node machines
- [ ] Cloud deployment options
- [ ] High availability Postgres
  - [ ] Use a PG operator

## Backup

Since the entire cluster is on a single VM, backups are simply an export
of the VM, compression, and then copying to a cloud bucket.
