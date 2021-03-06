import time
import logging
from typing import List

from spaceone.inventory.connector.aws_eks_connector.schema.data import Cluster, NodeGroup, Update, Tags
from spaceone.inventory.connector.aws_eks_connector.schema.resource import ClusterResource, ClusterResponse
from spaceone.inventory.connector.aws_eks_connector.schema.service_type import CLOUD_SERVICE_TYPES
from spaceone.inventory.libs.connector import SchematicAWSConnector


_LOGGER = logging.getLogger(__name__)
EXCLUDE_REGION = ['us-west-1']          # NOT SUPOORTED REGION


class EKSConnector(SchematicAWSConnector):
    service_name = 'eks'

    def get_resources(self) -> List[ClusterResource]:
        print("** EKS START **")
        resources = []
        start_time = time.time()

        collect_resource = {
            'request_method': self.request_data,
            'resource': ClusterResource,
            'response_schema': ClusterResponse
        }

        # init cloud service type
        for cst in CLOUD_SERVICE_TYPES:
            resources.append(cst)

        for region_name in self.region_names:
            if region_name in EXCLUDE_REGION:
                continue

            self.reset_region(region_name)
            resources.extend(self.collect_data_by_region(self.service_name, region_name, collect_resource))

        print(f' EKS Finished {time.time() - start_time} Seconds')
        return resources

    def request_data(self, region_name) -> List[Cluster]:
        paginator = self.client.get_paginator('list_clusters')
        response_iterator = paginator.paginate(
            PaginationConfig={
                'MaxItems': 10000,
                'PageSize': 50,
            }
        )

        for data in response_iterator:
            clusters = data.get('clusters', [])

            for _cluster_name in clusters:
                raw = self.client.describe_cluster(name=_cluster_name)

                if cluster := raw.get('cluster'):
                    cluster.update({
                        'updates': list(self.list_updates(_cluster_name)),
                        'node_groups': list(self.list_node_groups(_cluster_name)),
                        'account_id': self.account_id,
                        'tags': list(map(lambda tag: Tags(tag, strict=False),
                                         self.convert_tags(cluster.get('tags', {}))))
                    })
                    yield Cluster(cluster, strict=False)

    def list_node_groups(self, cluster_name):
        paginator = self.client.get_paginator('list_nodegroups')
        response_iterator = paginator.paginate(
            clusterName=cluster_name,
            PaginationConfig={
                'MaxItems': 10000,
                'PageSize': 50,
            }
        )

        for data in response_iterator:
            for node_group in data.get('nodegroups', []):
                node_group_response = self.client.describe_nodegroup(clusterName=cluster_name, nodegroupName=node_group)
                yield NodeGroup(node_group_response.get('nodegroup', {}), strict=False)

    def list_updates(self, cluster_name):
        paginator = self.client.get_paginator('list_updates')
        response_iterator = paginator.paginate(
            name=cluster_name,
            PaginationConfig={
                'MaxItems': 10000,
                'PageSize': 50,
            }
        )

        for data in response_iterator:
            for update_id in data.get('updateIds', []):
                response = self.client.describe_update(name=cluster_name, updateId=update_id)
                yield Update(response.get('update', {}), strict=False)

    @staticmethod
    def _convert_tag_format(tags):
        list_tags = []

        for _key in tags:
            list_tags.append({'key': _key, 'value': tags[_key]})

        return list_tags
