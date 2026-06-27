from remote_image_compare.domain.models import SourceConfig, SourceKind
from remote_image_compare.sources.local_source import LocalPathSource
from remote_image_compare.sources.sftp_source import SftpSource


def create_source(config: SourceConfig, auth=None, connection=None):
    if config.kind in {SourceKind.LOCAL, SourceKind.UNC}:
        return LocalPathSource(config)
    if config.kind is SourceKind.SFTP:
        source = SftpSource(config, auth=auth)
        if connection is not None:
            source.connect(
                host=connection.host,
                port=connection.port,
                username=connection.username,
            )
        return source
    raise ValueError(f"Unsupported source kind: {config.kind}")
