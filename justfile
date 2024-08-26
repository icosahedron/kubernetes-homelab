
set fallback

default:
    @just --choose

create-cluster:
    sudo kind create cluster --config yaml/config.kind.yaml
    -sudo helm repo add nfs-subdir-external-provisioner https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner

delete-cluster:
    sudo kind delete cluster -n homelab

install-nfs:
    helm install nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
      --set nfs.server=100.91.158.43 \
      --set nfs.path=/srv/nfs/k8s \
      --set storageClass.create=false
    sudo kubectl apply -f yaml/nfs-sc.yaml
     
    #     --set storageClass.name=nfs-client \
    #     --set storageClass.provisionerName=k8s-sigs.io/nfs-subdir-external-provisioner \
    #     --set storageClass.pathPattern='${.PVC.namespace}/${.PVC.name}' \
    #     --set storageClass.onDelete=retain
    # sudo kubectl apply -f yaml/nfs-sc.yaml
    # Failed experiment to have dynamic provisioning
    # helm upgrade --installl nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
    #      --set nfs.server=100.91.158.43 \
    #      --set nfs.path=/srv/nfs/k8s \
    #      --set storageClass.name=nfs-client \
    #      --set storageClass.provisionerName=k8s-sigs.io/nfs-subdir-external-provisioner \
    #      --set storageClass.pathPattern='${.PVC.namespace}/${.PVC.name}' \
    #      --set storageClass.onDelete=retain
    #      --set storageClass.create = true
    # sudo helm install nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner --set nfs.server=100.91.158.43 --set nfs.path=/srv/nfs/k8s

install-ingress:
    sudo kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

deploy-nginx:
    # sudo kubectl apply -f yaml/nginx-nfs-pv.yaml
    sudo kubectl apply -f yaml/nginx-nfs-pvc.yaml
    sudo kubectl apply -f yaml/nginx-pvc-deployment.yaml
    sudo kubectl wait --for=condition=available --timeout=60s deploy/nginx
    sudo kubectl apply -f yaml/nginx-service.yaml
    while [ -z $(sudo kubectl get svc/nginx -o jsonpath='{.spec.clusterIP}') ]; do \
       sleep 5; \
    done

delete-nginx:
    -sudo kubectl delete svc/nginx
    -sudo kubectl delete ingress/nginx-ingress
    -sudo kubectl delete deploy/nginx
    -sudo kubectl delete pvc/nginx
    # -sudo kubectl delete pv/nginx-nfs
