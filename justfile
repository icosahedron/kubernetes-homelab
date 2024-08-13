
set fallback

default:
    @just --choose

create-cluster:
    sudo kind create cluster --config yaml/config.kind.yaml
    -sudo helm repo add nfs-subdir-external-provisioner https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner

delete-cluster:
    sudo kind delete cluster -n homelab

install-nfs:
    sudo helm install nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner --set nfs.server=100.91.158.43 --set nfs.path=/srv/nfs/k8s

install-ingress:
    sudo kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

deploy-nginx:
    sudo kubectl apply -f yaml/nginx-nfs-pv.yaml
    sudo kubectl apply -f yaml/nginx-nfs-pvc.yaml
    sudo kubectl apply -f yaml/nginx-nfs-deployment.yaml
    sudo kubectl apply -f yaml/nginx-service.yaml

delete-nginx:
    -sudo kubectl delete deploy/nginx-nfs
    -sudo kubectl delete svc/nginx
    -sudo kubectl delete pvc/nginx-pvc
    -sudo kubectl delete pv/nginx-nfs
