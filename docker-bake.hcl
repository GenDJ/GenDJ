variable "RELEASE" {
    default = "0.0.7"
}

target "default" {
    dockerfile = "Dockerfile"
    tags = ["mrassisted/gendj:${RELEASE}"]
    contexts = {
        scripts = "./container-template"
        proxy = "./container-template/proxy"
    }
}
