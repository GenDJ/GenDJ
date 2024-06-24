variable "RELEASE" {
    default = "0.1.4"
}

target "default" {
    dockerfile = "Dockerfile"
    tags = ["mrassisted/gendj:${RELEASE}"]
    contexts = {
        scripts = "./container-template"
        proxy = "./container-template/proxy"
    }
}
