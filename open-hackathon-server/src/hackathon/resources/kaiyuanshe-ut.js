{
    "name": "sample-template-for-docker",
    "description": "",
    "virtual_environments":
    [
        {
            "provider": "docker",
            "type": "ubuntu terminal",
            "description":"",
            "name": "web",
            "ports":
            [
                {
                    "name": "website",
                    "port": 80,
                    "public": true,
                    "protocol": "tcp",
                    "url": "http://{0}:{1}"
                },
                {
                    "name": "ssh",
                    "port": 22,
                    "public": true,
                    "protocol": "tcp"
                }
            ],
            "remote":
            {
                "provider": "guacamole",
                "protocol": "ssh",
                "username": "root",
                "password": "root",
                "port": 22
            },
            "Hostname": "",
            "Domainname": "",
            "User": "",
            "AttachStdin": false,
            "AttachStdout": true,
            "AttachStderr": true,
            "Tty": true,
            "OpenStdin": true,
            "StdinOnce": false,
            "Env": [],
            "Cmd": ["/usr/sbin/sshd", "-D"],
            "Entrypoint": "",
            "Image": "rastasheep/ubuntu-sshd",
            "Labels": {},
            "Volumes": {},
            "WorkingDir": "",
            "NetworkDisabled": false,
            "MacAddress": "",
            "SecurityOpts": [""],
            "HostConfig":
            {
                "Binds": [],
                "Links": [],
                "LxcConf": {},
                "Memory": 0,
                "MemorySwap": 0,
                "CpuShares": 0,
                "CpusetCpus": "",
                "PortBindings": {},
                "PublishAllPorts": false,
                "Privileged": false,
                "ReadonlyRootfs": false,
                "Dns": [],
                "DnsSearch": [],
                "ExtraHosts": [],
                "VolumesFrom": [],
                "CapAdd": [],
                "CapDrop": [],
                "RestartPolicy": { "Name": "", "MaximumRetryCount": 0 },
                "NetworkMode": "",
                "Devices": [],
                "Ulimits": [],
                "LogConfig": { "Type": "json-file", "Config": {} },
                "CgroupParent": ""
            }
        }
    ]
}