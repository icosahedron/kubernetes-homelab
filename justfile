
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
    sudo kubectl apply -f yaml/nginx-pvc-deployment.yaml
    sudo kubectl wait --for=condition=available --timeout=300s deploy/nginx
    sudo kubectl apply -f yaml/nginx-service.yaml
    while [ -z $(sudo kubectl get svc/nginx -o jsonpath='{.spec.clusterIP}') ]; do \
       sleep 5; \
    done

delete-nginx:
    -sudo kubectl delete svc/nginx
    -sudo kubectl delete ingress/nginx-ingress
    -sudo kubectl delete deploy/nginx
    -sudo kubectl delete pvc/nginx
    -sudo kubectl delete pv/nginx-nfs

deploy-gitea:
    sudo kubectl apply -f yaml/gitea-nfs-pv.yaml
    sudo kubectl apply -f yaml/gitea-nfs-pvc.yaml
    sudo kubectl apply -f yaml/gitea-deployment.yaml
    while [ -z $(sudo kubectl get svc/gitea -o jsonpath='{.spec.clusterIP}') ]; do \
       sleep 5; \
    done

delete-gitea:
    -sudo kubectl delete ingress/gitea-ingress
    -sudo kubectl delete deploy/gitea
    -sudo kubectl delete svc/gitea
    -sudo kubectl delete pvc/gitea
    -sudo kubectl delete pv/gitea-nfs

