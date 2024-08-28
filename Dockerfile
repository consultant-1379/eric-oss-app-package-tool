ARG BASE_IMAGE_VERSION
FROM armdocker.rnd.ericsson.se/proj-am/sles/sles-pm:3.0.0-9

ARG HELM2_VERSION="v2.15.1"
ARG HELM3_VERSION="v3.4.2"

RUN curl -SsL https://get.helm.sh/helm-${HELM2_VERSION}-linux-amd64.tar.gz | tar xzf - linux-amd64/helm

RUN curl -SsL https://get.helm.sh/helm-${HELM3_VERSION}-linux-amd64.tar.gz -o  helm-${HELM3_VERSION}-linux-amd64.tar.gz
RUN mkdir -p linux-amd64-helm3 && tar -zxf helm-${HELM3_VERSION}-linux-amd64.tar.gz -C linux-amd64-helm3

COPY target/eric-oss-app-package-tool.tar.gz .
RUN tar -zxvf eric-oss-app-package-tool.tar.gz

FROM armdocker.rnd.ericsson.se/proj-am/releases/vnfsdk-pkgtools:1.2.0-1

COPY --from=0 --chown=root:root linux-amd64/helm /usr/local/bin/helm
COPY --from=0 --chown=root:root linux-amd64-helm3/linux-amd64/helm /usr/local/bin/helm3

COPY --from=0 eric-oss-app-package-tool .
RUN pip install eric_oss_app_package_tool-*.whl
COPY eric_oss_app_package_tool/vnfsdk_pkgtools/packager/csar.py /usr/lib/python2.7/site-packages/vnfsdk_pkgtools/packager/csar.py
WORKDIR "/target"

ENTRYPOINT ["eric-oss-app-package-tool"]
