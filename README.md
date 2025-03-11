# compliance-reporting-examples
[Contribution guidelines for this project](docs/CONTRIBUTING.md)

## Introduction

This repo explores how to leverage Cisco Network Services Orchestrator (NSO) compliance reporting to audit network configurations using compliance templates first introduced in NSO 6.1 and demonstrates the ongoing enhancements to compliance reporting. The repo explores several flavors of compliance check patterns, the process of creating an NSO compliance template, and an example framework for a continuous compliance reporting service that allows policy rules to be translated into built-in compliance reports.  

## Overview of Compliance Check Patterns

Several patterns emerge when creating compliance checks. In general, a compliance check can be described by 3 characteristics: the match type, the match pattern, and the match logic. Understanding which categories a compliance check falls into will help guide in selecting the appropriate template pattern to use.

To begin classifying a compliance check, you must first create the intended network configuration for the PASS condition and/or the FAIL condition (as appropriate). This configuration is then assessed for each of the categories below. 

### Match Type

The match type category determines any required conditions for a given configuration to be matched. This has template implications as variables must be referenced and regular expression conditions must be well understood. 

1. exact match

    ```
    service password-encryption
    ```

2. variable substitution

    ```
    clock timezone EST -5
    ```

3.  regular expression match 

    
    ```
    login block-for 900 attempts 3 within 120
    ```

### Match Logic

The match logic category determines how a given configuration is evaluated. This has template implications as features may need to be present, absent, present but disabled, absent but enabled, or evaluated (ie count).

1. enabled feature

    ```
    service password-encryption
    ```

2. disabled feature

    ```
    no mpls ip propagate-ttl
    ```
    
3. absent configuration

    ```
    service ipv4 tcp-small-servers
    ```
    
4. comparison operations (ex. 2 or more ntp servers)

    ```
    ntp server 1.1.1.1
    ntp server 2.2.2.2
    ```

### Match Pattern

The match pattern category determines the scope of a given configuration match. This has template implications as configuration elements may be nested, may require matching multiple lines, or may require iterating through a list of values.

1. global configuration

    ```
    service password-encryption
    ```
    
2. nested configuration

    ```
    interface GigabitEthernet0/1
      no ip unreachables
    ```
    
3. configuration list

    ```
    ip access-control list XXX
      deny
      deny
      deny
      deny ip any any option any-options
      permit

    ```
    
4. configuration section (multiple lines)

    ```
    archive
      log config
        logging enable
    ```

## Creating Compliance Templates

The following sections demonstrate how to create compliance templates from common compliance patterns. 

### Example exact match

Create a compliance template from the (1) exact match, (2) enabled feature, (3) global configuration item: `service password-encryption`
```
compliance template service-encrypt
 ned-id cisco-ios-cli-6.108
  config
   service password-encryption
```

### Example variable match

Create a compliance template from the (1) variable substitution, (2) enabled feature, (3) global configuration item: `clock timezone EST -5` 
```
compliance template timezone
 ned-id cisco-ios-cli-6.108
  config
   clock timezone {$TIMEZONE}
   clock timezone {$OFFSET_HOURS}
   clock timezone {$OFFSET_MINUTES}

```

### Example absent match

Create a compliance template from the (1) regular expression match, (2) absent feature, (3) global configuration item: `service ipv4 tcp-small-servers` and `service ipv4 udp-small-servers`
```
compliance template service-small-servers
 ned-id cisco-ios-cli-6.108
  config
   ! Tags: absent
   service udp-small-servers
   ! Tags: absent
   service tcp-small-servers
```

### Example regex match

Create a compliance template from the (1) regular expression and variable match, (2) enabled feature, (3) nested configuration item: `.*deny ip any any option any-options`
```
compliance template acl_deny_options
 ned-id cisco-ios-cli-6.108
  config
   ip access-list extended {$IPV4_PROTECT}
    ".*deny ip any any option any-options"
```

### Example configuration section

Create a compliance template from the (1) variable match, (2) enabled feature, (3) configuration block: `line console 0; exec-timeout 0; login authentication SECURE_AUTH`
```
compliance template line_console_strict
 ned-id cisco-ios-cli-6.108
  config
   ! Tags: strict
   line console 0
    exec-timeout 0
    login authentication {$AUTH_NAME}
```

### Example nested match

Create a compliance template from the (1) regex match, (2) enabled feature, (3) nested match: `interface GigabitEthernet 0/0; no ip unreachables`
```
compliance template unreachable
 ned-id cisco-ios-cli-6.108
  config
   ! Tags: allow-empty
   interface GigabitEthernet .*
    ip unreachables false
   !
   ! Tags: allow-empty
   interface TenGigabitEthernet .*
    ip unreachables false
```

## Overview of Compliance Service Package

The compliance service provides a framework for defining policy and policy scope which then translates policy intent into built-in compliance reports. The service includes constructs for template variable re-use, simplification in definitions through groups, and future integration with device and/or service templates for remediation.

### Prerequisites
1. NSO 6.4.3 or higher version is required
2. Python 3.9 or higher version is required

### Basic Usage

A compliance service instance is first defined by a policy name (ex. ios-xe-baseline-policy) and then by defining the devices, templates, and template variables associated with the policy. The policy scope maybe a single device or multiple device (ex. device-group). Multiple compliance templates may exist under each rule name. 

Sample compliance service:
```
compliance-service ios-xe-baseline-policy
 policy-scope single-device
 single-device
  device XE0
  rules service-checks
   compliance-templates service-encrypt
   compliance-templates service-small-servers
```

Furthermore, the compliance service is augmented with a resource data model (rdm) for pre-defined variable definitions as well as a group feature for compliance templates and rules. 

Sample resource data model for pre-defined variables:
```
rdm-compliance pre-defined-variables
 template-variables DEFAULT_OFFSET_HOURS
  var-key   OFFSET_HOURS
  var-value -5
 !
 template-variables DEFAULT_OFFSET_MINMUTES
  var-key   OFFSET_MINUTES
  var-value 0
 !
 template-variables DEFAULT_TIMEZONE
  var-key   TIMEZONE
  var-value EST
```

Sample resource data model for groups
```
rdm-compliance groups
 compliance-template-groups ios-xe-services
  compliance-templates service-encrypt
  compliance-templates service-small-servers
```

Sample compliance service referencing pre-defined variables
```
no compliance-service ios-xe-baseline-policy
compliance-service ios-xe-baseline-policy
 policy-scope single-device
 single-device
  device XE0
  rules service-checks
   apply-compliance-tmpl-grp [ ios-xe-services ]
  ! 
  rules mgmt-checks
   compliance-templates timezone
    pre-defined-variables [ DEFAULT_OFFSET_HOURS DEFAULT_OFFSET_MINMUTES DEFAULT_TIMEZONE ]
```

The resulting compliance report may now be validated as created in NSO:
```
admin@ncs# show running-config compliance reports 
compliance reports report ios-xe-baseline-policy_XE0
 device-check device [ XE0 ]
 device-check template service-encrypt
 !
 device-check template service-small-servers
 !
 device-check template timezone
  variable OFFSET_HOURS
   value -5
  !
  variable OFFSET_MINUTES
   value 0
  !
  variable TIMEZONE
   value EST
```

