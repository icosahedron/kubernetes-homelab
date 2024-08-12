# Set up a Web Server in a Kubernetes Cluster in Docker with NFS Shares

# **A Homelab**

Setting up a homelab is a great way to learn about technologies.

This homelab is set up using [KinD](https://kind.sigs.k8s.io/), the Kubernetes in Docker version of K8s, on an Ubuntu 24.04 VM. All nodes will be on the same VM in docker containers.

Networking is on a [Tailscale](https://tailscale.com/) VPN, so each machine has an IP address of 100.x.x.x.

The [Github repo](notion://www.notion.so/icosahedron20/Archive-5b2e656921644fb1be2b87059c4d1db7?p=7c1efe1091e64c2d97113af4ab90ae9f&pm=s) for this configuration contains the yaml files referenced in this article.

## **Install Docker for Containers**

Docker is required for this configuration, so install it if it's not available. See the [official Docker documentation](https://docs.docker.com/engine/install/ubuntu) for instructions on installing Docker.

## **Install NFS for Persistent Volumes**

NFS is a common provider of K8s persistent volumes. Azure and AWS (and probably Google) use NFS to mount persistent volumes (among other tech).

This homelab will create an NFS server and mount it as a client on the same VM.

Creating this server is only to approximate a cloud environment somewhat.

### **Export the NFS directory**

Create the directory that will serve the files via NFS:

```
mkdir -p /srv/nfs/k8s
```

Create or add to the /etc/exports file the entry:

```
/srv/nfs/k8s 172.0.0.0/8(rw,sync,no_subtree_check,no_root_squash)
```

This tells the NFS server that IP addresses in Docker's IP range (172.x.x.x) are allowed to mount this directory, along with some security options.

Restart the NFS server with `sudo systemctl restart nfs-kernel-server`.

(Instructions taken from [LearnLinux.TV](https://www.learnlinux.tv/how-to-set-up-an-nfs-server-on-ubuntu-complete-with-autofs/).)

## **Create the cluster**

To bring up the cluster, use the `config.kind.yaml` file in the `yaml` directory.

```
kind create cluster --config yaml/config.kind.yaml
```

This will bring up the cluster with a control plane and two workers (as defined
at the time of this writing).

## **Install the Ingress**

Next, install the `ingress-nginx` ingress controller to handle network traffic into the cluster.

`kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml`

This will install the most recent version of `ingress-nginx` from the github repo directly.

## **Install NFS Provisioner**

Helm is required to install the provisioner for NFS, so install it first with `sudo apt install helm`.

Once helm is installed, the NFS provisioner can be installed with configuration information about the NFS server and export path to use.

In this cluster, the command would look like

```
helm repo add nfs-subdir-external-provisioner https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/
helm install nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
    --set nfs.server=100.x.x.x \
    --set nfs.path=/srv/nfs/k8s
```

since we have previously exported the `/srv/nfs/k8s` directory in the `/etc/exports` file.

(Instructions from their [Github repo](https://github.com/kubernetes-sigs/nfs-subdir-external-provisioner).)

## **Test the website**

Now it's time to test the configuration of the cluster.

Let's install a web server and see if it can read a file off the NFS share. Look in the `yaml` directory for files to deploy an nginx web server configured to read files off the NFS share.

Deploy these with the following commmands:

```bash
sudo kubectl apply -f nfs-pv.yaml
sudo kubectl apply -f nfs-pvc.yaml
sudo kubectl apply -f nfs-web-deployment.yaml
sudo kubectl apply -f nfs-web-service.yaml
```

Put a test `index.html` file in `/srv/nfs/k8s`. Save the following (or whatever you want) to that path.

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

If this is what you see, congratulations, you have set up Kubernetes cluster
with an NFS share.

