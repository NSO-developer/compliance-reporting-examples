# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service


def build_vars_dict(var_path, vars_dict):
    """
    Updates variable dictionary with key value pairs

    Args:
        var_path: mgaaic path for variables under template or pre-defined
        vars_dict: Dictionary that stores all variables
    """
    #Add key value pair for each variable
    vars_dict[var_path.var_key] = var_path.var_value

def build_template_dict(root, template_path, template_dict):
    """
    Updates template dictionary with variables for template.
    
    Variable inheritence order for each template
    Higher takes precedence and overwrites lower 
    1. variables defined under template
    2. variables defined in pre-defined-variables

    Args:
        root: Root node
        template: maagic path for templates under rules or group
        template_dict: Dictionary that stores all templates
    """
    #Iterate through each template in template path
    for template in template_path:
        #Retrieve existing variables if template already exists
        temp_vars = template_dict[template.template_name] if template.template_name in template_dict else {}
        #Add variables for pre-defined-variables
        for pre_vars in template.pre_defined_variables:
            path = root.rdm_compliance.pre_defined_variables.template_variables[pre_vars]
            build_vars_dict(path, temp_vars)
        #Add variables defined under template
        for tmp_vars in template.template_variables:
            build_vars_dict(tmp_vars, temp_vars)
        template_dict[template.template_name] = temp_vars

def build_rules_dict(root, rule_path, rules_dict):
    """
    Updates rules dictionary with rule meta data and template information

    Template inheritence order for each rule
    Higher takes precedence and overwrites lower 
    1. Templates defined under the rule
    2. Templates defined and applied via template groups

    Args:
        root: Root node
        rule_path: maagic path for compliance rules
        rules_dict: Dictionary that stores all rules
    """
    #Iterate through each rule in rule list
    for rule in rule_path:
        #Retrieve existing templates if rule already exists        
        if rule.rule_name in rules_dict:
            if 'remediation_templates' in rules_dict[rule.rule_name]:
                remed_tmpl_dict = rules_dict[rule.rule_name]['remediation_templates']
            else:
                remed_tmpl_dict = {}
            if 'compliance_templates' in rules_dict[rule.rule_name]:
                comp_tmpl_dict = rules_dict[rule.rule_name]['compliance_templates']
            else:
                comp_tmpl_dict = {}
            rules_dict[rule.rule_name]['rule_description'] = rule.rule_description
        else:
            remed_tmpl_dict = {}
            comp_tmpl_dict = {}
            rules_dict[rule.rule_name] = {'rule_description': rule.rule_description}
        #Write meta data to rule
        for meta_data_field in rule.rule_meta_data:
            if 'rule_meta_data' in rules_dict[rule.rule_name]:
                rules_dict[rule.rule_name]['rule_meta_data'][meta_data_field.field_name] = meta_data_field.field_value
            else:
                rules_dict[rule.rule_name]['rule_meta_data'] = {meta_data_field.field_name : meta_data_field.field_value}
        #Add remediation templates for templates applied via template groups
        for remed_tmpl_group in rule.apply_remediation_tmpl_grp:
            template_path = root.rdm_compliance.groups.device_template_groups[remed_tmpl_group]
            build_template_dict(root, template_path.device_templates, remed_tmpl_dict)
        #Add remediation templates for templates defined under rule
        build_template_dict(root, rule.remediation_templates, remed_tmpl_dict)
        rules_dict[rule.rule_name]['remediation_templates'] = remed_tmpl_dict
        #Add compliance templates for templates applied via template groups
        for comp_tmpl_group in rule.apply_compliance_tmpl_grp:
            template_path = root.rdm_compliance.groups.compliance_template_groups[comp_tmpl_group]
            build_template_dict(root, template_path.compliance_templates, comp_tmpl_dict)
        #Add compliance templates for templates defined under rule
        build_template_dict(root, rule.compliance_templates, comp_tmpl_dict)
        rules_dict[rule.rule_name]['compliance_templates'] = comp_tmpl_dict

def create_compliance_report_parameters(report, rules_dict):
    """
    Creates compliance report parameters based on rule dictionary

    Args:
        report: maagic path for compliance report
        rules_dict: Dictionary that stores all rules
    """
    #Add compliance templates from rules_dict
    for rule in rules_dict:
        #If template exists via another rule, vars will be merged 
        # due to existing compliance-report support. If unique variables
        # desired, create unique template names
        for template in rules_dict[rule]['compliance_templates']:
            if not report.device_check.template.exists(template):
                report.device_check.template.create(template)
                tmp = report.device_check.template[template]
            else:
                tmp = report.device_check.template[template]
            #Add vars to template
            for var in rules_dict[rule]['compliance_templates'][template]:
                if not tmp.variable.exists(var):
                    tmp.variable.create(var)
                    var_key = tmp.variable[var]
                else:
                    var_key = tmp.variable[var]
                var_key.value = rules_dict[rule]['compliance_templates'][template][var] 

# ------------------------
# SERVICE CALLBACK EXAMPLE
# ------------------------
class ServiceCallbacks(Service):

    # The create() callback is invoked inside NCS FASTMAP and
    # must always exist.
    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        self.log.info('Service create(service=', service._path, ')')
        #Rule inheritence order for the policy
        #Higher takes precedence and overwrites lower 
        #1. Rules defined under the policy
        #2. Rules defined and applied via rules group

        #Logic for single device
        if service.policy_scope == 'single-device':
            device = service.single_device.device
            report_name = f'{service.policy_name}_{device}'
            rules_dict = {}
            #Add rules applied via rules group
            for rule_grp in service.single_device.apply_rules_group:
                rule_path = root.rdm_compliance.groups.rules_groups[rule_grp].rules
                build_rules_dict(root, rule_path, rules_dict)
            #Add rules applied under policy 
            build_rules_dict(root, service.single_device.rules, rules_dict)
            #Create report
            root.ncs__compliance.reports.report.create(report_name)
            report = root.ncs__compliance.reports.report[report_name]
            report.device_check.create()
            #Add single-device to report
            report.device_check.device = [device]

        #Logic for multiple device via device leaf-list or device-group
        elif service.policy_scope == 'multiple-devices':
            devices = service.multiple_devices.devices
            device_groups = service.multiple_devices.device_groups
            report_name = f'{service.policy_name}_multiple-devices'
            rules_dict = {}
            #Add rules applied via rules group
            for rule_grp in service.multiple_devices.apply_rules_group:
                rule_path = root.rdm_compliance.groups.rules_groups[rule_grp].rules
                build_rules_dict(root, rule_path, rules_dict)
            #Add rules applied under policy 
            build_rules_dict(root, service.multiple_devices.rules, rules_dict)
            #Create report
            root.ncs__compliance.reports.report.create(report_name)
            report = root.ncs__compliance.reports.report[report_name]
            report.device_check.create()
            #Add devices and device-group to report
            report.device_check.device = devices
            report.device_check.device_group = device_groups

        #Log rules dict
        self.log.info(rules_dict)
        
        #Create compliance report parameters
        create_compliance_report_parameters(report, rules_dict)
            
        #vars = ncs.template.Variables()
        #vars.add('DUMMY', '127.0.0.1')
        #template = ncs.template.Template(service)
        #template.apply('compliance-service-template', vars)

    # The pre_modification() and post_modification() callbacks are optional,
    # and are invoked outside FASTMAP. pre_modification() is invoked before
    # create, update, or delete of the service, as indicated by the enum
    # ncs_service_operation op parameter. Conversely
    # post_modification() is invoked after create, update, or delete
    # of the service. These functions can be useful e.g. for
    # allocations that should be stored and existing also when the
    # service instance is removed.

    # @Service.pre_modification
    # def cb_pre_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service premod(service=', kp, ')')

    # @Service.post_modification
    # def cb_post_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service postmod(service=', kp, ')')


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        # The application class sets up logging for us. It is accessible
        # through 'self.log' and is a ncs.log.Log instance.
        self.log.info('Main RUNNING')

        # Service callbacks require a registration for a 'service point',
        # as specified in the corresponding data model.
        #
        self.register_service('compliance-service-servicepoint', ServiceCallbacks)

        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')
