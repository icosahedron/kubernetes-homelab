
set fallback

default:
    @just --choose

create-cluster:
    kind create cluster --config yaml/config.kind.yaml
    # -sudo helm repo add nfs-subdir-external-provisioner https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner

delete-cluster:
    kind delete cluster -n homelab

install-nfs:
    helm install nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner --set nfs.server=100.91.158.43 --set nfs.path=/srv/nfs/k8s
    # sudo kubectl rollout status deployment 

install-ingress:
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
    kubectl rollout status deployment ingress-nginx-controller -n ingress-nginx

deploy-nginx:
    helm install nginx helm/nginx --namespace web --create-namespace
    kubectl rollout status deployment nginx -n web
    # sudo kubectl apply -f yaml/nginx-nfs-pv.yaml
    # sudo kubectl apply -f yaml/nginx-nfs-pvc.yaml
    # sudo kubectl apply -f yaml/nginx-pvc-deployment.yaml
    # sudo kubectl wait --for=condition=available --timeout=60s deploy/nginx
    # sudo kubectl apply -f yaml/nginx-service.yaml
    # sudo kubectl wait --for=condition=ready --timeout=60s svc/nginx

delete-nginx:
    helm uninstall nginx -n web
    -kubectl wait --for=delete pods -l role=web-frontend -n web
    # -sudo kubectl delete svc/nginx
    # -sudo kubectl delete ingress/nginx-ingress
    # -sudo kubectl delete deploy/nginx
    # -sudo kubectl delete pvc/nginx
    # -sudo kubectl delete pv/nginx-nfs

deploy-postgres:
    helm install postgres helm/postgres --namespace db --create-namespace
    kubectl rollout status sts postgres-postgresql -n db

delete-postgres:
    helm uninstall postgres -n db
    -kubectl wait --for=delete pods -l role=db -n db

deploy-smb:
    helm template smb-csi helm/smb > smb-csi.yaml
    kapp deploy -f smb-csi.yaml --app smb-csi -y

delete-smb:
    kapp delete --app smb-csi -y
