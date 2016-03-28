import os
from urlparse import urlparse

import requests
from plumbum.cmd import git, tar


def mkdir_p(path):
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        os.makedirs(path)
    return path

ENRIQUE_DIR = mkdir_p("~/.mesos-magellan/enrique")
PACKAGES_DIR = mkdir_p(os.path.join(ENRIQUE_DIR, "packages"))


def get_package_cls(name, url):
    package_cls = None
    url_parsed = urlparse(url)
    if url_parsed.scheme == "git":
        package_cls = GitRepo
    elif url_parsed.scheme in ["http", "https"]:
        if url.endswith("tar.gz"):
            package_cls = GzipArchive

    if package_cls is None:
        raise ValueError

    return package_cls


def get_problem_path(name, url):
    package_cls = get_package_cls(name, url)
    package = package_cls(name, url)
    package.fetch()
    return package.problem_path


class Package(object):
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self._problem_path = None
        os.makedirs(self.package_path)

    def fetch(self):
        raise NotImplementedError

    @property
    def problem_path(self):
        return self._problem_path

    @property
    def package_path(self):
        package_home = os.path.join(PACKAGES_DIR, self.name)
        return package_home

    def download_http(self):
        localfile_path = self._download_file(self.url, self.package_path)
        return localfile_path

    @staticmethod
    def _download_file(url, download_path):
        """Download file from url

        http://stackoverflow.com/a/16696317/1798683
        """
        local_filename = os.path.join(download_path, url.split('/')[-1])
        r = requests.get(url, stream=True)
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
        return local_filename


class Archive(Package):
    def _extract_package(self, localfile_path):
        raise NotImplementedError

    def fetch(self):
        localfile_path = self.download_http()
        problem_path = self._extract_package(localfile_path)
        self._problem_path = problem_path


class GzipArchive(Archive):
    def _extract_package(self, localfile_path):
        dirname = os.path.split(localfile_path)[-1].split(".")[0]
        dirpath = os.path.join(self.package_path, dirname)
        os.makedirs(dirpath)
        tar.run("-xzf {archive} -C {target_dir}".format(
            archive=localfile_path,
            target_dir=dirpath
        ))
        return dirpath


class GitRepo(Package):
    def fetch(self):
        local_dirname = os.path.join(self.package_path,
                                     self.url.split('/')[-1])
        if not os.path.exists(local_dirname):
            git.run("clone {url} {local_dirname}")
        else:
            # If repo exists, pull instead of cloning
            git.run("-C {local_dirname} pull")
        self._problem_path = local_dirname
