{ pkgs ? import <nixpkgs> { } }:

with pkgs;

let 
  backupScript = pkgs.writeTextDir "app/backup.sh" (builtins.readFile ./backup.sh);
in
  pkgs.dockerTools.buildImage { 
    name = "gitea-backup";
    tag = "latest";
    
    copyToRoot = buildEnv {
      name = "gitea-rclone";
      paths = [ gitea rclone bash busybox backupScript ];
      pathsToLink = [ "/bin" "/app" ];
    };
    extraCommands = ''
      busybox addgroup git
      busybox adduser git git
    '';
    config = {
      Cmd = [ "/bin/busybox" "ash" "/app/backup.sh" ];
      WorkingDir = "/app";
    };
  }
 
#    backupScript = pkgs.writeTextDir "app/backup.sh" (builtins.readFile ./backup.sh);

# in 
#   buildImage {
#    copyToRoot = buildEnv {
#       name = "backup-script";
#       path = [ backupScript ];
#       pathToLink = [ "/app" ];
#     };

#     config = {
#       Cmd = [ "/bin/busybox" "ash" "/backup.sh" ];
#       WorkingDir = "/app";
#       User = "1000:1000"; # Example non-root user
#     };

#     # extraFiles = {
#     #   "/app/backup.sh" = backupScript;
#     # };

#     extraCommands = ''
#       run chmod +x /app/backup.sh
#     '';
#   }
