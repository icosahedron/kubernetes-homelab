
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
    # kapp deploy -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml --app ingress-nginx -y
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
    kubectl rollout status deployment ingress-nginx-controller -n ingress-nginx

deploy-nginx: deploy-smb install-ingress
    helm template nginx helm/nginx > nginx-helm.yaml
    kapp deploy -f nginx-helm.yaml --app nginx -y

delete-nginx:
    kapp delete --app nginx -y

deploy-postgres:
    helm template postgres helm/postgres > postgres-helm.yaml
    kapp deploy -f postgres-helm.yaml --app postgres -y
    # helm install postgres helm/postgres --namespace db --create-namespace
    # kubectl rollout status sts postgres-postgresql -n db

delete-postgres:
    kapp delete --app postgres -y
    # helm uninstall postgres -n db
    # -kubectl wait --for=delete pods -l role=db -n db

deploy-smb:
    helm template smb-csi helm/smb > smb-csi.yaml
    kapp deploy -f smb-csi.yaml --app smb-csi -y

delete-smb:
    kapp delete --app smb-csi -y


