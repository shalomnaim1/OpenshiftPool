import re
import sys
import argparse
import itertools
import datetime

from openshift_pool.openshift.cluster import OpenshiftClusterBuilder
from openshift_pool.env import config_workspace_as_cwd
from openshift_pool.common import NodeType, pgrep, set_proc_name
from openshift_pool.openshift.stack import StackBuilder


config_workspace_as_cwd()
PROCESS_NAME = 'openshiftdeployer'


parser = argparse.ArgumentParser()


operation_subparser = parser.add_subparsers(dest='operation', help='operation')

create_parser = operation_subparser.add_parser('create', help='Creating a cluster stack without deploy')
create_parser.add_argument('--master_count', type=int, default=1, action='store',help='The count of master nodes')
create_parser.add_argument('--infra_count', type=int, default=1, action='store',help='The count of infra nodes')
create_parser.add_argument('--compute_count', type=int, default=3 ,action='store',help='The count of compute nodes')
create_parser.add_argument('--owner', type=str, action='store',help='The owner of the stack')

deploy_parser = operation_subparser.add_parser('deploy', help='Deploying a cluster')
deploy_parser.add_argument('--version', default="latest",action='store', help='The openshift version to deploy')
deploy_parser.add_argument('--master_count', type=int, default=1, action='store',help='The count of master nodes')
deploy_parser.add_argument('--infra_count', type=int, default=1, action='store',help='The count of infra nodes')
deploy_parser.add_argument('--compute_count', type=int, default=3 ,action='store',help='The count of compute nodes')
deploy_parser.add_argument('--owner', type=str, action='store',help='The owner of the stack')

delete_parser = operation_subparser.add_parser('delete', help='Deleting a cluster')
delete_parser.add_argument('cluster_name', action='store', help='The name of the cluster')
delete_parser.add_argument('--owner', type=str, action='store',help='The owner of the stack')

def parse_commend(namespace):

    def is_positive(num):
        return num > 0

    def is_stack_exist(stack_name):
        return bool(StackBuilder().is_stack(stack_name))

    def is_valid_version(version):
        return bool(re.match('\d\.\d', version))

    def is_supported_version(version):
        return version not in OpenshiftClusterBuilder().SUPPORTED_VERSIONS

    def validate_args(namespace):

        deploy_args = ["master_count", "infra_count", "compute_count", "version"]
        create_args = ["master_count", "infra_count", "compute_count"]
        delete_args = ["cluster_name"]

        action_dict = {"create": create_args, "deploy": deploy_args, "delete": delete_args}

        test_dict = {"master_count": [is_positive], "infra_count": [is_positive], "compute_count": [is_positive],
                     "version": [is_valid_version, is_supported_version], "cluster_name": [is_stack_exist()]}
        general_valid = True
        invalid_param_names = []

        # Validate if all args are valid
        for arg in action_dict[namespace.operation]:
            # all the required checks for specific arg finished successfully and is_valid was never with false value
            is_valid = all([test(getattr(namespace, arg)) for test in test_dict[arg]])
            if not is_valid:
                invalid_param_names.append(arg)

            general_valid = general_valid and is_valid
        return  (general_valid, invalid_param_names)

    def create(namespace):
        master_nodes = StackBuilder.get_node_name("master", namespace.master_count)
        infra_nodes = StackBuilder.get_node_name("infra", namespace.infra_count)
        compute_nodes = StackBuilder.get_node_name("compute", namespace.compute_count)

        node_names = itertools.chain(*[master_nodes, infra_nodes, compute_nodes])
        stack_name = f"{namespace.owner}-{namespace.owner.replace(',','')}-{datetime.datetime.now().strftime('%m%d%y-%H%M%S')}"
        StackBuilder.create(stack_name, node_names, [NodeType.MASTER] * namespace.master_count +
                                                    [NodeType.INFRA] * namespace.infra_count +
                                                    [NodeType.COMPUTE] * namespace.compute_count)

    def deploy(namespace):
        pass

    def delete(namespace):
        pass
    tasks_dict = {"create": create, "deploy":deploy, "delete":delete}

    is_valid, wrong_params = validate_args(namespace)
    if not is_valid:
        print(f"Parameters validation failed for one or more parameters: {wrong_params}")
        sys.exit(1)

    if namespace.operation in ('create', 'deploy'):

        cluster = OpenshiftClusterBuilder().create(
                namespace.cluster_name, node_types, namespace.version
            )
            print('Openshift cluster has successfully deployed.')
            print('-'*50)
            print(cluster.master_nodes[0].ssh.exec_command('oc version')[1].read())
            print('Nodes:')
            print(cluster.master_nodes[0].ssh.exec_command('oc get nodes')[1].read())
            print('-'*50)

        elif namespace.operation == 'create':
            print(f'Creating stack {namespace.cluster_name}.')
            stack = StackBuilder().create(
                namespace.cluster_name, OpenshiftClusterBuilder().gen_node_names(node_types), node_types)
            print('\nStack has successfully created.')
            print('-'*50)
            for node in stack.instances:
                print(node.fqdn)
            print('-'*50)

    if namespace.operation == 'delete':
        cluster = OpenshiftClusterBuilder().get(namespace.cluster_name)
        if namespace.force and input(
                f'Are you sure you want to delete cluster {namespace.cluster_name}? (y/n) ').lower() != 'y':
            print('Canceling operation.')
            return
        OpenshiftClusterBuilder().delete(cluster)
        print(f'\nCluster {namespace.cluster_name} has been successfully deleted.')


def main():
    if pgrep(PROCESS_NAME):
        print('Can only run 1 process at once.')
        return
    set_proc_name(PROCESS_NAME.encode())
    parse_commend(parser.parse_args())


if __name__ == '__main__':
    main()
