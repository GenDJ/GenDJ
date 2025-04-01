variable "RELEASE" {
    default = "0.3.4"
}

target "default" {
    dockerfile = "Dockerfile"
    tags = ["mrassisted/gendj:${RELEASE}"]
    context = "."
    contexts = {
        scripts = "./container-template"
        proxy = "./container-template/proxy"
    }
}

target "networked" {
    dockerfile = "Dockerfile.networked"
    tags = ["mrassisted/gendj-networked:${RELEASE}"]
    context = "."
    contexts = {
        scripts = "./container-template"
        proxy = "./container-template/proxy"
    }
}

target "serverless" {
    dockerfile = "Dockerfile.serverless"
    tags = ["mrassisted/gendj-serverless:${RELEASE}"]
    context = "."
}