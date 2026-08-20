"""Baseline IE (Independent Engineering) report template.

Imported from the G4 ESS DNV Technology Review workbook (Aug 2026): the
"00 DNV Master Index" tab for the section list and owners, and each numbered
section tab for its review items. Editable at /ie/templates.
"""

SRC = "https://docs.google.com/spreadsheets/d/1Z3rXOmKf4czMs4BHSZTXwVkXCawRgLGEs8aaeo1_lks/edit"

# (code, title, primary owner, [ {item_id, sub_section, review_item, evidence,
#                                  suggested_owner, priority, source} ])
DNV_ESS_SECTIONS = [('01 Introduction',
  '1. Introduction',
  'DNV / CE',
  [{'item_id': '1.1',
    'sub_section': 'Objective of Review',
    'review_item': 'Define technology-review and bankability objectives for TPOs, investors and '
                   'financiers',
    'evidence': 'Review Objective and Bankability Scope Statement',
    'suggested_owner': 'DNV',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 1'},
   {'item_id': '1.2',
    'sub_section': 'Scope of Review',
    'review_item': 'Define included battery, BMS, ESS inverter, controller, backup equipment, '
                   'cloud and integrated-system scope',
    'evidence': 'System Scope and Review-Boundary Document',
    'suggested_owner': 'DNV',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 1'},
   {'item_id': '1.3',
    'sub_section': 'Product Configurations Reviewed',
    'review_item': 'Define the reviewed minimum, standard, maximum, PV-coupled, backup and '
                   'multi-unit configurations and lock the applicable BOM, BMS and firmware '
                   'baseline',
    'evidence': 'Product Configuration Matrix; Final BOM/BMS/Firmware Baseline',
    'suggested_owner': 'DNV',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 1'},
   {'item_id': '1.4',
    'sub_section': 'Review Methodology',
    'review_item': 'Document design review, test-report review, factory audit, interviews, '
                   'field-data review and lifetime modeling',
    'evidence': 'DNV Review Plan; Data Request List; Review Methodology',
    'suggested_owner': 'DNV',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 1'},
   {'item_id': '1.5',
    'sub_section': 'Assumptions and Limitations',
    'review_item': 'Identify exclusions, pending work, prior-generation evidence and confidential '
                   'information',
    'evidence': 'Assumption, Limitation and Open-Item Register',
    'suggested_owner': 'DNV',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 1'}]),
 ('02 Company Evaluation',
  '2. Company and Business Evaluation',
  'RBO planning',
  [{'item_id': '2.1',
    'sub_section': 'Company Overview',
    'review_item': 'Provide company profile, ESS organization and global business footprint',
    'evidence': 'Corporate presentation; audited financials; product history; patents; capacity '
                'plan',
    'suggested_owner': 'RBO planning / CE',
    'priority': 'Medium',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 2'},
   {'item_id': '2.2',
    'sub_section': 'Financial and Business Stability',
    'review_item': 'Demonstrate financial capacity, credit support and parent backing, where '
                   'applicable, for long-term warranty and service obligations',
    'evidence': 'Audited financials; credit or liquidity evidence; warranty support structure; '
                'applicable parent support',
    'suggested_owner': 'RBO planning',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 2'},
   {'item_id': '2.3',
    'sub_section': 'Energy Storage Product History',
    'review_item': 'Summarize G1-G4 roadmap, installed base, operating years, markets and '
                   'customers',
    'evidence': 'Corporate presentation; audited financials; product history; patents; capacity '
                'plan',
    'suggested_owner': 'RBO planning / CE',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 2'},
   {'item_id': '2.4',
    'sub_section': 'R&D Capability',
    'review_item': 'Describe the development organization, engineering responsibility, '
                   'laboratories, reliability capability and relevant product-development '
                   'experience',
    'evidence': 'Corporate presentation; audited financials; product history; patents; capacity '
                'plan',
    'suggested_owner': 'PO planning / CE',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 2'},
   {'item_id': '2.6',
    'sub_section': 'Production Capacity and Continuity',
    'review_item': 'Provide factory capacity, ramp-up, manufacturing locations and '
                   'business-continuity plans',
    'evidence': 'Corporate presentation; audited financials; product history; patents; capacity '
                'plan',
    'suggested_owner': 'PO planning / CE',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 2'}]),
 ('03 Product Overview',
  '3. G4 ESS Product Overview',
  'CE / Product PM',
  [{'item_id': '3.1',
    'sub_section': 'Development Background',
    'review_item': 'Explain market needs, TPO/bankability requirements and G3 lessons driving G4 '
                   'development',
    'evidence': 'G4 Product Requirements TPO/Market Requirement Summary G3 Lessons Learned and G4 '
                'Design-Response Summary',
    'suggested_owner': 'PS&P / Dev. PM / CE',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 3'},
   {'item_id': '3.2',
    'sub_section': 'Product Portfolio',
    'review_item': 'List model numbers, capacity, power, installation and backup options',
    'evidence': 'Datasheet',
    'suggested_owner': 'Dev. PM',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 3'},
   {'item_id': '3.3',
    'sub_section': 'Product Specifications',
    'review_item': 'Confirm energy, power, efficiency, temperature, enclosure, size, weight and '
                   'communications',
    'evidence': 'Datasheet',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 3'},
   {'item_id': '3.4',
    'sub_section': 'System Architecture',
    'review_item': 'Provide electrical, communication, energy-flow and protection architecture',
    'evidence': 'Architecture drawings; configuration matrix;',
    'suggested_owner': 'HW : Dev. PM SW : Kyoungmo Koo (PS&P SW)',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 3'},
   {'item_id': '3.5',
    'sub_section': 'Configuration and Scalability',
    'review_item': 'Define minimum/maximum battery configurations, parallel operation, expansion '
                   'and backup arrangements',
    'evidence': 'Operation use case',
    'suggested_owner': 'Dev. PM',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 3'},
   {'item_id': '3.6',
    'sub_section': 'G3-to-G4 Improvements',
    'review_item': 'Create an evidence-based matrix covering performance, reliability, safety, '
                   'installation, software and service',
    'evidence': 'G3-to-G4 comparison',
    'suggested_owner': 'Dev. PM / PS&P',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 3'}]),
 ('04 Battery Evaluation',
  '4. Battery System Technical Evaluation',
  'Dev. PM',
  [{'item_id': '4.1',
    'sub_section': 'Battery Cell Evaluation',
    'review_item': 'Assess supplier, chemistry, format, specifications, production history and '
                   'market position',
    'evidence': 'Cell specification',
    'suggested_owner': 'Dev PM / LGENSOL',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'},
   {'item_id': '4.2',
    'sub_section': 'Cell Performance',
    'review_item': 'Validate capacity, C-rate, resistance, efficiency and temperature/SOC '
                   'performance',
    'evidence': 'Cell/module specifications raw test data BMS design documents thermal test '
                'reports',
    'suggested_owner': 'Dev PM / LGENSOL',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'},
   {'item_id': '4.3',
    'sub_section': 'Cell Cycle-Life',
    'review_item': 'Provide raw cycle-life data across SOC, DOD, C-rate and temperature conditions',
    'evidence': 'Cell test reports',
    'suggested_owner': 'Dev PM / LGENSOL',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'},
   {'item_id': '4.4',
    'sub_section': 'Cell Calendar-Life',
    'review_item': 'Provide empirical calendar-aging data, projections and model methodology '
                   'across temperature and SOC',
    'evidence': 'Cell test reports',
    'suggested_owner': 'Dev PM / LGENSOL',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'},
   {'item_id': '4.5',
    'sub_section': 'Module/Pack Design',
    'review_item': 'Review mechanical/electrical architecture, busbars, fuses, sensors, contactors '
                   'and isolation',
    'evidence': 'Battery module design',
    'suggested_owner': 'Dev PM / LGENSOL',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'},
   {'item_id': '4.6',
    'sub_section': 'Pack Performance',
    'review_item': 'Validate pack energy, power, efficiency, imbalance, SOC/SOE accuracy and power '
                   'cycling',
    'evidence': 'Battery module test report',
    'suggested_owner': 'Dev PM / LGENSOL',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'},
   {'item_id': '4.7',
    'sub_section': 'Battery Management System',
    'review_item': 'Review monitoring, estimation, balancing, alarms, fault escalation and '
                   'independent protection',
    'evidence': 'BMS design documents',
    'suggested_owner': 'Dev PM / LGENSOL',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'},
   {'item_id': '4.8',
    'sub_section': 'Thermal Management',
    'review_item': 'Validate cooling/heating, cell-temperature distribution, hotspots, derating '
                   'and component reliability',
    'evidence': 'Thermal test reports',
    'suggested_owner': 'Dev PM / LGENSOL',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'},
   {'item_id': '4.9',
    'sub_section': 'Environmental Characteristics',
    'review_item': 'Confirm temperature, humidity, altitude, enclosure, corrosion, water exposure '
                   'and noise limits',
    'evidence': 'Environmental test reports',
    'suggested_owner': 'Dev PM / LGENSOL',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'},
   {'item_id': '4.10',
    'sub_section': 'Battery Reliability and Lifetime Assessment',
    'review_item': 'Consolidate cell, module, pack, BMS and thermal-component reliability, '
                   'degradation, technical EOL and 15-year warranty alignment',
    'evidence': 'Cell and pack life reports BMS/component reliability data degradation model '
                'failure statistics technical EOL and warranty justification',
    'suggested_owner': 'LGENSOL  RETC for Battery+BMS test',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 4'}]),
 ('05 ESS Inverter',
  '5. ESS Inverter Technical Evaluation',
  'Dev. PM',
  [{'item_id': '5.1',
    'sub_section': 'ESS Inverter Overview',
    'review_item': 'Describe the G4 internal ESS inverter architecture and interfaces with the '
                   'battery and system controls',
    'evidence': 'ESS Inverter Architecture Block Diagram Battery, Controller and Grid Interface '
                'Description',
    'suggested_owner': 'Dev. PM',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Inverter section'},
   {'item_id': '5.2',
    'sub_section': 'Power Conversion Topology and Design',
    'review_item': 'Document DC/DC, DC/AC, isolation, switching topology and critical power '
                   'components',
    'evidence': 'inverter/pcs design doc.',
    'suggested_owner': 'Dev. PM',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Inverter section'},
   {'item_id': '5.3',
    'sub_section': 'Technical Specifications',
    'review_item': 'Confirm voltage/current range, charge/discharge power, continuous/peak output '
                   'and backup ratings',
    'evidence': 'inverter/pcs specifications',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Inverter section'},
   {'item_id': '5.4',
    'sub_section': 'Inverter Output and Dynamic Performance',
    'review_item': 'Validate rated/peak AC output, command tracking, response time, ramp rate, '
                   'load steps, overload, THD and power factor',
    'evidence': 'inverter/pcs performance test report',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Inverter section'},
   {'item_id': '5.5',
    'sub_section': 'Conversion Efficiency',
    'review_item': 'Validate full-load, partial-load and standby efficiency across operating '
                   'conditions',
    'evidence': 'inverter/pcs performance test report',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Inverter section'},
   {'item_id': '5.6',
    'sub_section': 'Thermal Performance and Power Derating',
    'review_item': 'Validate temperature-dependent output, component temperatures and design '
                   'margin',
    'evidence': 'inverter/pcs thermal reports',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Inverter section'},
   {'item_id': '5.7',
    'sub_section': 'Grid-Connected Functions',
    'review_item': 'Validate export control, ride-through, reactive-power functions and '
                   'regional/utility profiles',
    'evidence': 'Grid profile code lists',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Inverter section'},
   {'item_id': '5.8',
    'sub_section': 'Backup and Off-Grid Performance',
    'review_item': 'Validate transfer, black start, overload, motor starting and load-step '
                   'response',
    'evidence': 'inverter/pcs performance test report',
    'suggested_owner': 'Dev. PM',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Inverter section'},
   {'item_id': '5.9',
    'sub_section': 'Inverter Reliability and Component Lifetime',
    'review_item': 'Assess semiconductor, capacitor, relay/contactor, cooling-component and '
                   'power-supply lifetime using derating, MTBF/FIT and accelerated testing',
    'evidence': 'Inverter/pcs DFMEA component lifetime model certificates',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Inverter section'}]),
 ('06 Compliance',
  '6. Regulatory Compliance and Safety',
  'Dev. PM',
  [{'item_id': '6.1',
    'sub_section': 'Applicable Codes and Standards',
    'review_item': 'Map UL 9540, UL 1973, UL 1741 SB, IEEE 1547/1547.1, NEC, NFPA 855, IFC, IRC, '
                   'UN 38.3, FCC, EMC and conditionally applicable IEC requirements',
    'evidence': 'UL9540,  UL9540A 5th Ed. (Unit level test) UL 9540A — Installation / Large-Scale '
                'Fire Test UL 1973 (Battery safety) UL 62109 / IEC 62109 (PCS / inverter safety) '
                'UL 1741 SB (Grid-Support Functions) IEEE 1547 / 1547.1 (Interconnection Standard) '
                'IEC 62116 (Anti-Islanding)',
    'suggested_owner': 'Certification',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 5'},
   {'item_id': '6.2',
    'sub_section': 'Safety Architecture',
    'review_item': 'Document hardware/software protection, isolation, ground-fault, shutdown and '
                   'redundancy',
    'evidence': 'System Protection Architecture Protection-Function Matrix Safety-Related '
                'Electrical Schematics',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 5'},
   {'item_id': '6.3',
    'sub_section': 'System Hazard Analysis',
    'review_item': 'Cover fire, thermal runaway, shock, overcharge, short circuit, sensor and '
                   'communication failures',
    'evidence': 'Certificates UL reports hazard analysis protection matrix code-compliance '
                'evidence',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 5'},
   {'item_id': '6.4',
    'sub_section': 'Fault Response Matrix',
    'review_item': 'Map detection, warning, derating, shutdown, latching, reset and recovery',
    'evidence': 'Certificates UL reports hazard analysis protection matrix code-compliance '
                'evidence',
    'suggested_owner': 'Dev. PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 5'},
   {'item_id': '6.5',
    'sub_section': 'Installation Code Compliance',
    'review_item': 'Validate NFPA 855, IFC, IRC and AHJ installation requirements including '
                   'spacing, energy limits, indoor/outdoor use, garage, egress and fire-test-based '
                   'conditions',
    'evidence': 'NFPA 855 (2026)-compliant IOM + IFC 2024 / IRC alignment;  installation '
                'limitations applicable AHJ or large-scale-fire justification',
    'suggested_owner': 'Dev. PM',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Section 5'}]),
 ('07 Controls Software',
  '7 Controls, Software and Cybersecurity',
  'PS&P, CIO',
  [{'item_id': '7.1',
    'sub_section': 'Control Architecture',
    'review_item': 'Map local controllers, BMS, ESS inverter, gateway, cloud and communications',
    'evidence': 'System Control and Communication Diagram Component Interface List Communication '
                'Method Description',
    'suggested_owner': 'PS&P / SW PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Controls and software '
              'section'},
   {'item_id': '7.2',
    'sub_section': 'Energy Management Functions',
    'review_item': 'Define self-consumption, TOU, backup, export control, demand response and VPP '
                   'modes',
    'evidence': 'Energy Management Function Description Operating Mode Logic Supported Function '
                'List',
    'suggested_owner': 'PS&P / SW PM',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Controls and software '
              'section'},
   {'item_id': '7.3',
    'sub_section': 'Operating Mode Validation',
    'review_item': 'Validate transitions, scheduling, export limits, forecasts and outage behavior',
    'evidence': 'G4 ESS System DVT or Software Functional Test Report Operating Mode and '
                'Transition Test Results Export Control and Backup Operation Test Results',
    'suggested_owner': 'PS&P / SW PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Controls and software '
              'section'},
   {'item_id': '7.5',
    'sub_section': 'Software Development Lifecycle',
    'review_item': 'Document requirements, design, coding, V&V, release and configuration '
                   'management',
    'evidence': 'Software Development Process Document Software Requirement List Software Test and '
                'Release Approval Records',
    'suggested_owner': 'PS&P / SW PM',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Controls and software '
              'section'},
   {'item_id': '7.6',
    'sub_section': 'Firmware Update and Recovery',
    'review_item': 'Document firmware and BMS version control, OTA authorization, rollback, '
                   'recovery, cybersecurity updates and supported service life',
    'evidence': 'Firmware Update and Rollback Procedure Firmware Update and Recovery Test Report '
                'BMS/Inverter/Controller Software Compatibility List Software Update and Support '
                'Policy',
    'suggested_owner': 'PS&P / SW PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Controls and software '
              'section'},
   {'item_id': '7.7',
    'sub_section': 'Software Reliability',
    'review_item': 'Validate response to communication loss, cloud outage, reset, data loss and '
                   'watchdog events',
    'evidence': 'Communication Loss, Cloud Outage, System Reset and Watchdog Test Results Failure '
                'Recovery Test Report',
    'suggested_owner': 'PS&P / SW PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Controls and software '
              'section'},
   {'item_id': '7.8',
    'sub_section': 'Monitoring and Data',
    'review_item': 'Describe the monitoring functions, available data, alarms, user access and '
                   'data retention for PRO (installer), Home (end user), and Fleet Manager '
                   '(portfolio and fleet management). Please include   - Main functions of each '
                   'platform  - Available monitoring data and alarms  - User roles and access '
                   'levels  - Data sampling intervals and retention periods  - Representative '
                   'screenshots or sample data exports  - API or external data access methods, if '
                   'supported',
    'evidence': '• PRO – Installer platform for commissioning, configuration, firmware checks, '
                'system diagnostics, and troubleshooting • Home – End-user platform for monitoring '
                'energy production, consumption, battery SOC, operating modes, and alerts • Fleet '
                'Manager – Portfolio-level platform for fleet monitoring, system status, alarm '
                'management, performance comparison, and data management',
    'suggested_owner': 'PS&P / SW PM',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Controls and software '
              'section'},
   {'item_id': '7.9',
    'sub_section': 'Cybersecurity Controls',
    'review_item': 'Document device, data and network security, secure boot, encryption, access '
                   'control, vulnerability management and available cybersecurity attestation',
    'evidence': 'Product Cybersecurity Overview Cybersecurity Risk Assessment Software Patch and '
                'Vulnerability Handling Procedure Third-Party Security Test Report, if available',
    'suggested_owner': 'PS&P / SW PM',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Controls and software '
              'section'}]),
 ('08 Installation',
  '8. Installation and System Integration',
  'Dev. PM',
  [{'item_id': '8.1',
    'sub_section': 'Installation Architecture',
    'review_item': 'Document mechanical, electrical, communication and PV/grid/load connections',
    'evidence': 'Installation manual',
    'suggested_owner': 'System Integration / Field',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Installation section'},
   {'item_id': '8.2',
    'sub_section': 'Site Requirements',
    'review_item': 'Define mounting, clearance, ventilation, environmental and hazard requirements',
    'evidence': 'Installation manual',
    'suggested_owner': 'System Integration / Field',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Installation section'},
   {'item_id': '8.3',
    'sub_section': 'Installation Process',
    'review_item': 'Provide the controlled installation workflow and IOM, including tooling, '
                   'wiring, torque, registration and error-prevention controls',
    'evidence': 'Installation manual',
    'suggested_owner': 'System Integration / Field',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Installation section'},
   {'item_id': '8.4',
    'sub_section': 'Commissioning',
    'review_item': 'Validate commissioning, firmware/configuration checks, battery health, '
                   'functional acceptance tests and installer/customer handover',
    'evidence': 'Commissioning procedure and checklist acceptance-test record '
                'firmware/configuration check handover form',
    'suggested_owner': 'System Integration / Field',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Installation section'},
   {'item_id': '8.5',
    'sub_section': 'Installer Qualification',
    'review_item': 'Define certification, training, audits and refresher requirements',
    'evidence': 'Installation manual site requirements commissioning procedure training materials',
    'suggested_owner': 'System Integration / Field',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Installation section'},
   {'item_id': '8.6',
    'sub_section': 'Integrated ESS Validation',
    'review_item': 'Validate battery, ESS inverter, controller, meter, gateway, cloud, backup and '
                   'grid interfaces',
    'evidence': 'Integrated System DVT Report System Interface and Compatibility Matrix End-to-End '
                'Backup Grid and Communication Test Results',
    'suggested_owner': 'System Integration / Field',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Installation section'},
   {'item_id': '8.7',
    'sub_section': 'External PV System Compatibility',
    'review_item': 'Define supported external PV-system interfaces and limitations without '
                   'requiring a specific PV inverter platform',
    'evidence': 'Operation use case',
    'suggested_owner': 'System Integration / Field',
    'priority': 'Medium',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Installation section'}]),
 ('09 Mfg Quality Supply',
  '9. Manufacturing, Quality and Supply Chain',
  'GEO / System Procurement / Dev. PM',
  [{'item_id': '9.1',
    'sub_section': 'Manufacturing Overview and Production Readiness',
    'review_item': 'Identify manufacturing responsibilities, production locations, line readiness, '
                   'production capacity, ramp-up plan and the latest audit status for the G4 '
                   'production line.',
    'evidence': 'Manufacturing Responsibility Matrix Factory and Production-Line Overview '
                'Production Capacity and Ramp-Up Plan ISO 9001/14001 Certificates Latest G4 '
                'Factory Audit Report and CAPA Closure Records',
    'suggested_owner': 'GEO',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Manufacturing and quality '
              'section'},
   {'item_id': '9.2',
    'sub_section': 'Supplier Qualification and Supply-Chain Risk',
    'review_item': 'Assess critical-supplier qualification, incoming controls, single-source '
                   'dependency, lead-time risk, alternative sourcing and supply-continuity plans.',
    'evidence': 'Approved Supplier List Critical Supplier Risk Matrix Supplier Audit Reports or '
                'Scorecards Incoming Inspection Plan Dual-Source and Supply-Continuity Plan',
    'suggested_owner': 'System Procurement',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Manufacturing and quality '
              'section'},
   {'item_id': '9.3',
    'sub_section': 'Manufacturing Process Control',
    'review_item': 'Document critical manufacturing processes, IPQC, error-proofing and '
                   'end-of-line acceptance criteria.',
    'evidence': 'Manufacturing Process Flow Production Control Plan Critical Process Work '
                'Instructions IPQC Checklist End-of-Line Test Specification and Result Summary '
                'Production Yield Report',
    'suggested_owner': 'GEO',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Manufacturing and quality '
              'section'},
   {'item_id': '9.4',
    'sub_section': 'Product Traceability',
    'review_item': 'Demonstrate traceability from cell and critical-component lots to the '
                   'finished-product serial number, including installed firmware.',
    'evidence': 'Traceability Procedure Serialization and Lot-Mapping Rules Sample Product '
                'Genealogy Record Cell/Module/PCB/Firmware-to-Unit Traceability Record '
                'Traceability-System Screenshots',
    'suggested_owner': 'GEO',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Manufacturing and quality '
              'section'},
   {'item_id': '9.5',
    'sub_section': 'Nonconformance and CAPA',
    'review_item': 'Document how manufacturing and field issues are recorded, investigated, '
                   'corrected and verified for closure.',
    'evidence': 'NCR and CAPA Procedure Sample 8D or Root-Cause Report Rework and Repair Procedure '
                'Corrective-Action Verification and Closure Record',
    'suggested_owner': 'GEO',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Manufacturing and quality '
              'section'},
   {'item_id': '9.6',
    'sub_section': 'Change Management and Final Configuration Control',
    'review_item': 'Control BOM, component, firmware and process changes and confirm that '
                   'certifications and test reports apply to the final production configuration.',
    'evidence': 'ECR/ECO/PCN Procedure Change-Control Board Process Change-Impact Assessment Final '
                'BOM/BMS/Firmware Baseline Sample Change Approval and Retest Decision',
    'suggested_owner': 'GEO',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Manufacturing and quality '
              'section'},
   {'item_id': '9.7',
    'sub_section': 'Conditional Regulatory Supply-Chain Compliance',
    'review_item': 'For applicable TPO or regulated-country business, provide consolidated DCA, '
                   'FEOC/PFE, country-of-origin and supplier-compliance evidence.',
    'evidence': 'DCA Eligib',
    'suggested_owner': 'GEO / System Procurement',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Manufacturing and quality '
              'section'},
   {'item_id': '9.8',
    'sub_section': 'Change Management',
    'review_item': 'Control BOM, component, firmware and process changes and demonstrate that '
                   'certifications, DNV evidence and third-party tests apply to the final '
                   'production configuration',
    'evidence': 'ECR/ECO/PCN procedure final BOM/BMS/firmware applicability matrix '
                'certification/test impact and retest decisions',
    'suggested_owner': 'GEO / System Procurement',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026) - Manufacturing and quality '
              'section'},
   {'item_id': '9.9',
    'sub_section': 'Conditional Regulatory Supply-Chain Compliance',
    'review_item': 'For applicable TPO or regulated-country business, maintain one consolidated '
                   'DCA, FEOC/PFE, origin and supplier-declaration package without expanding these '
                   'into separate DNV report sections',
    'evidence': 'DCA Eligibility Letter or Technical Memo Notice 2025-08 Safe-Harbor Calculation '
                'Summary Applicable SKU, Factory and BOM Revision Matrix Country-of-Origin and Key '
                'Supplier Supporting Documents Supplier Declarations & Non-FEOC/PFE Certifications '
                'FEOC/PFE Legal Memo and MACR Calculation',
    'suggested_owner': 'GEO / Dev. PM',
    'priority': 'Critical',
    'source': 'Conditional TPO / Regulatory Requirement'}]),
 ('10 Reliability DVT',
  '10. Reliability and Design Validation',
  'System Quailty',
  [{'item_id': '10.1',
    'sub_section': 'Reliability Requirements and Prediction',
    'review_item': 'Define the G4 ESS design life, warranty life, mission profile, availability '
                   'target and expected system/component failure rates.',
    'evidence': 'G4 ESS Reliability Requirements Specification Product Mission Profile System and '
                'Component MTBF/FIT Prediction Report Key Component Lifetime and Derating Analysis',
    'suggested_owner': 'Dev. PM / SQA - Phase 1  RETC - Phase 2',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 reliability evidence '
              'gap'},
   {'item_id': '10.2',
    'sub_section': 'System-Level FMEA',
    'review_item': 'Identify critical failure modes and controls for the battery, BMS, ESS '
                   'inverter, contactors, controller, communications and cloud functions.',
    'evidence': 'G4 ESS System DFMEA/FMEA Critical Failure-Mode Summary Risk-Reduction Action and '
                'Closure Records',
    'suggested_owner': 'Dev. PM / SQA - Phase 1  RETC - Phase 2',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 reliability evidence '
              'gap'},
   {'item_id': '10.3',
    'sub_section': 'Reliability and Design Validation',
    'review_item': 'Validate electrical, thermal, environmental, mechanical, functional, backup '
                   'and communication reliability under normal and accelerated conditions and '
                   'confirm closure of any major issues affecting the final product.',
    'evidence': 'G4 ESS DVP&R G4 ESS DVT Summary Report ALT/HALT and Environmental Test Reports '
                'Reliability Demonstration Test Report, if performed Test Configuration and BOM '
                'Matrix Final Pass/Fail Summary Major Issue and Retest Closure Summary, if '
                'applicable',
    'suggested_owner': 'Dev. PM / SQA - Phase 1  RETC - Phase 2',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 reliability evidence '
              'gap'},
   {'item_id': '10.4',
    'sub_section': 'Third-Party Testing',
    'review_item': 'Confirm that independent tests use the final or representative G4 '
                   'configuration and include clear sample selection, acceptance criteria and '
                   'failure disposition.',
    'evidence': 'Third-Party Test Plan and Test Matrix RETC Test Reports Tested Product '
                'Configuration and Sample List Major Deviation and Retest Closure Summary, if '
                'applicable',
    'suggested_owner': 'RETC - Phase 2',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 reliability evidence '
              'gap'},
   {'item_id': '10.5',
    'sub_section': 'Field Reliability and G3 Evidence Applicability',
    'review_item': 'Provide available G4 beta and field reliability data. If G3 field data is used '
                   'to support the G4 assessment, explain the relevant design similarities, '
                   'differences and evidence applicability.',
    'evidence': 'G4 Beta/Field Reliability Summary, if available G4 RMA and Failure Data, if '
                'available G3 Field/RMA Summary, only if used G3-to-G4 Design Change and Evidence '
                'Applicability Matrix, only if prior-generation evidence is used',
    'suggested_owner': 'PS&P / FA',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 reliability evidence '
              'gap'}]),
 ('11 Service Warranty',
  '11. Service Infrastructure, Warranty and O&M',
  'System Quailty, CS&Engineering',
  [{'item_id': '11.1',
    'sub_section': 'Service Organization and Performance',
    'review_item': 'Describe th service organization, support coverage, technical-support levels, '
                   'escalation process, response targets and available service-performance '
                   'results.',
    'evidence': 'Service Organization Chart Service Coverage Map Technical Support and Escalation '
                'Flow Service SLA Response Time, RMA Turnaround and Repeat-Failure KPI Summary',
    'suggested_owner': 'CS',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 service/warranty '
              'findings'},
   {'item_id': '11.2',
    'sub_section': 'Remote Monitoring and Diagnostics',
    'review_item': 'Describe how system alerts, monitoring data and remote diagnostic functions '
                   'are used to identify and troubleshoot system and fleet-level issues.',
    'evidence': 'Remote Monitoring and Diagnostics Overview Alarm and Fault-Code List Remote '
                'Troubleshooting Workflow Representative PRO and Fleet Manager Screenshots Sample '
                'Diagnostic Case',
    'suggested_owner': 'CS',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 service/warranty '
              'findings'},
   {'item_id': '11.3',
    'sub_section': 'RMA, Spare Parts and Serviceability',
    'review_item': 'Define the RMA process, replacement logistics, spare-parts availability, '
                   'field-replaceable components, expected service time and labor/transport '
                   'responsibilities.',
    'evidence': 'RMA Process Flow Spare-Parts List and Inventory Plan Replacement Logistics and '
                'Turnaround Targets Field-Replacement Procedure Labor and Transportation '
                'Responsibility Matrix',
    'suggested_owner': 'CS',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 service/warranty '
              'findings'},
   {'item_id': '11.4',
    'sub_section': 'Warranty Terms and Remedies',
    'review_item': 'Define the product and performance warranty, capacity/throughput terms, '
                   'remedies, exclusions, transferability and labor/transport coverage.',
    'evidence': 'G4 ESS Product Warranty Performance/Capacity and Throughput Warranty Schedule '
                'Warranty Remedy Matrix Warranty Exclusions and Transfer Rules Labor and '
                'Transportation Coverage Policy',
    'suggested_owner': 'CS',
    'priority': 'High',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 service/warranty '
              'findings'},
   {'item_id': '11.5',
    'sub_section': 'Warranty Financial Support',
    'review_item': 'Explain how long-term warranty obligations are financially supported through '
                   'reserves, insurance, parent support or another credible mechanism.',
    'evidence': 'Warranty Reserve Methodology or Summary Warranty Claim Assumptions Insurance or '
                'Parent Support Evidence, if applicable Extended-Warranty or TPO Support Plan, if '
                'applicable',
    'suggested_owner': 'CS',
    'priority': 'Critical',
    'source': 'DNV residential ESS technology-review benchmark (2026); G3 service/warranty '
              'findings'}]),
 ('12 Conclusions',
  '12. Conclusions and Recommendations',
  'DNV / CE',
  [{'item_id': '12.1',
    'sub_section': 'Overall Technology Assessment',
    'review_item': 'Consolidate the overall technical conclusion and evidence basis',
    'evidence': 'Consolidated findings; risk register; closure plan; re-review schedule',
    'suggested_owner': 'DNV',
    'priority': 'Critical',
    'source': 'G4 bankability/TPO objective; consolidated DNV review'},
   {'item_id': '12.2',
    'sub_section': 'G3-to-G4 Improvements',
    'review_item': 'Summarize closed G3 issues and remaining G4 validation needs',
    'evidence': 'Consolidated findings; risk register; closure plan; re-review schedule',
    'suggested_owner': 'CE / PS&P',
    'priority': 'Critical',
    'source': 'G4 bankability/TPO objective; consolidated DNV review'},
   {'item_id': '12.3',
    'sub_section': 'TPO and Bankability',
    'review_item': 'Summarize long-term performance, service, warranty, supply-chain compliance '
                   'and lifecycle implications',
    'evidence': 'Consolidated findings; risk register; closure plan; re-review schedule',
    'suggested_owner': 'DNV',
    'priority': 'Critical',
    'source': 'G4 bankability/TPO objective; consolidated DNV review'},
   {'item_id': '12.4',
    'sub_section': 'Remaining Risks',
    'review_item': 'List material technical, manufacturing, certification, service and data risks',
    'evidence': 'Consolidated findings; risk register; closure plan; re-review schedule',
    'suggested_owner': 'DNV',
    'priority': 'Critical',
    'source': 'G4 bankability/TPO objective; consolidated DNV review'},
   {'item_id': '12.5',
    'sub_section': 'Follow-up Actions',
    'review_item': 'Assign owners and dates for required evidence and risk closure',
    'evidence': 'Consolidated findings; risk register; closure plan; re-review schedule',
    'suggested_owner': 'DNV / CE',
    'priority': 'Critical',
    'source': 'G4 bankability/TPO objective; consolidated DNV review'}])]

BASELINE = {
    "name": "DNV ESS Technology Review (G4 baseline)",
    "reviewer": "DNV",
    "category": "ESS",
    "notes": "Imported from the G4 ESS DNV Technology Review workbook, Aug 2026.",
    "sections": DNV_ESS_SECTIONS,
}
