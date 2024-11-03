
set fallback

default:
    @just --choose

create-cluster: check-tools
    kind create cluster --config yaml/config.kind.yaml

delete-cluster: delete-nginx delete-postgres
    kind delete cluster -n homelab

install-nfs-subdir:
    helm install nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner --set nfs.server=100.91.158.43 --set nfs.path=/srv/nfs/k8s

install-nfs-server:
    helm template nfs-server helm/nfs-server --namespace default --set architecture=$(uname -m) > nfs-server-helm.yaml
    kapp deploy --app nfs-server -f nfs-server-helm.yaml -y
    helm repo add csi-driver-nfs https://raw.githubusercontent.com/kubernetes-csi/csi-driver-nfs/master/charts
    helm template csi-driver-nfs csi-driver-nfs/csi-driver-nfs --namespace kube-system --version v4.9.0 > nfs-csi-driver-helm.yaml
    kapp deploy --app csi-driver-nfs -f nfs-csi-driver-helm.yaml -y

install-smb:
    helm template smb-csi helm/smb > smb-csi.yaml
    kapp deploy -f smb-csi.yaml --app smb-csi -y

delete-smb:
    kapp delete --app smb-csi -y

install-ingress:
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
    kubectl rollout status deployment ingress-nginx-controller -n ingress-nginx

install-reflector:
    kapp deploy -f https://github.com/emberstack/kubernetes-reflector/releases/latest/download/reflector.yaml --app secret-config-reflector -y

deploy-nginx: install-nfs-server install-ingress
    helm template nginx helm/nginx > nginx-helm.yaml
    kapp deploy -f nginx-helm.yaml --app nginx -y

delete-nginx:
    kapp delete --app nginx -y

deploy-postgres: install-nfs-server
    helm template postgres helm/postgres > postgres-helm.yaml
    kapp deploy -f postgres-helm.yaml --app postgres -y

delete-postgres:
    kapp delete --app postgres -y

deploy-gitea: install-nfs-server install-ingress install-reflector deploy-postgres
    helm template gitea helm/gitea > gitea-helm.yaml
    kapp deploy -f gitea-helm.yaml --app gitea -y

delete-gitea:
    kapp delete --app gitea -y

# Check if required tools are installed
check-tools:
    #!/usr/bin/env bash
    REQUIRED_TOOLS=("kind" "docker" "helm" "kapp")
    MISSING_TOOLS=()

    # Function to check if a command exists
    check_command() {
        if ! command -v "$1" >/dev/null 2>&1; then
            MISSING_TOOLS+=("$1")
            return 1
        fi
        return 0
    }

    # Check each required tool
    echo "Checking for required tools..."
    for tool in "${REQUIRED_TOOLS[@]}"; do
        if check_command "$tool"; then
            echo "✓ $tool is installed"
        else
            echo "✗ $tool is not installed"
        fi
    done

    # If any tools are missing, exit with error
    if [ ${#MISSING_TOOLS[@]} -ne 0 ]; then
        echo -e "\nError: The following required tools are missing:"
        for tool in "${MISSING_TOOLS[@]}"; do
            echo "- $tool"
        done
        exit 1
    fi

    echo -e "\nAll required tools are installed!"
