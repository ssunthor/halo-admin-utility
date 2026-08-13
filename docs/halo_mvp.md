# Defense Halo 1.0 (MVP)

**Product Manager:** Bill Radman
**Product Ops Owner:** Georgi Georgiev
**EPIC link:** PRDCT-4900 - Defense Halo 1.0 (MVP) In Progress
**PRD Status:** PRDCT-4901 - Product Requirements (PRD) In Progress
**PRD Actual Population Date:** April 3, 2026
**RTO Status:** PRDCT-4902 - Release to Operations (RTO) Done
**Preliminary Release Date:** 
**Target Release Date:** 30 Sep 2026

*Please note if the population target date is missed, the preliminary release date is no longer valid. The target release date is dictated by the actual population date.*

## 📗 Product Story

### Background & justification
The cyber security threat landscape has entered the AI era. You now must secure your network against real-time, agent-driven attacks. Time is the enemy. The time to identify and remediate vulnerabilities before they can be exploited.
The attacker is now AI native, breakout time has collapsed, threat and vulnerability exploitation has outpaced patching, regulatory pressure is escalating, and the attack surface is expanding.

### Positioning
Developed by a CISO for CISOs, GTT Defense Halo is an AI-native security platform that reduces enterprise risk by accelerating detection, investigation, and response—cutting time to remediation while delivering real-time, network-speed protection across an ever-expanding attack surface.
GTT Defense Halo is an AI-native security platform designed to proactively identify, analyze, and respond to threats across an enterprise network. GTT Defense Halo doesn’t just react to attacks; it hunts for anomalies and indicators of compromise before they escalate into breaches. GTT Defense Halo operates at network speed continuously collecting and analyzing a wide range of security data, applying sophisticated analytics, and actionable intelligence to strengthen enterprise security posture.

### Use Cases & Customer Needs
* Assess deployed device policies relative to known security frameworks to identify compliance gaps & vulnerabilities with AI recommendations to mitigate.
* Real time correlation of CVE notifications to deployed inventory of devices and software with AI recommendations to mitigate potential exploits.
* Correlate Security Logs and Netflow data from firewalls, network devices, hosts, and endpoints to learn normal behavior.
* Digital fingerprint security events to identify deviations from normal behavior and reveal specific types of anomalies.
* Provide classified, correlated, & risk scored alarms.
* Calculate a single consolidated indicator of current risk across a customer estate.
* Visibility to all active network connections & host anomaly levels.
* Display view of all customer WAN traffic flows across the globe.
* Provide leading indicators of heightened network risk activity.
* Expose insights into unusual spikes in user access behavior and auth failures.
* Identify host hot spots for anomalies.
* Identify host hot spots for admin changes.

---

## 🗒️ Product Requirements
Additional product requirements for future phases should be captured separately in an Additional PRD.

### Quote2Cash
Here is the desired traditional quote-to-cash process: Dynamics 365 CRM opportunity --> EnvisionDX quote model --> customer approves quote --> PON & SOF created in CMD --> customer docusigns SOF --> attaches to PON in CMD --> PON changes status to Service Delivery --> then to Provisioning --> CMD invoice auto generates monthly --> invoice recorded in Oracle ERP ledger

### Quote
Most customers should have a single Defense Halo subscription unless they have data sovereignty regulations that requires them to have completely separate regional instances of Halo AI models, asset inventory, notification engine, and portal. In this latter case, the customer must subscribe to a separate Halo subscription per region for all components to be regionally isolated. Each Defense Halo subscription holds a single service term and single currency that applies to all selected services within the subscription.

Direct and indirect sellers should be able to select the one or more services desired by the customer to include in their Defense Halo subscription and an asset count tier for each service. They should also be able to apply discounts up to field authorized levels off of list prices for the Defense Halo subscription as follows:
* Apply a discount to total Defense Halo subscription monthly fees.
* and Apply a discount to total Defense Halo subscription install fees.
* -or- Apply individual discounts to individual Defense Halo service monthly fees.
* and Apply individual discounts to individual Defense Halo service install fees.

The deal desk and product management should be able to authorize discounts that exceed field authorized level and have them applied to the quote in the same manner as above via the standard processes and resources.

The generated quote sent to the customer for review and signature should display the Defense Halo subscription noting selected services and tiers with MRR and NRR list prices, any applied discounts, and net prices by service and total for the Defense Halo subscription.

Standard quoting of Defense Halo subscriptions should allow one-year service terms initially with the ability for the deal desk and product management to authorize subscription quotes with custom service terms beyond one-year and have them applied to the quote via the standard quoting processes and resources.

The one-year service term prices summarized in the following tables are to be used to generate the monthly fee and corresponding install fee on the quote for each selected Defense Halo service at the chosen asset count tier for each.

**Monthly Price USD**

| Halo Service Asset Count Tier | Configuration Recon | CVE Recon | Halo Detect | Halo Command (detect is a prerequisite) | Field Authorized Discounts (1 year list 25%) |
| --- | --- | --- | --- | --- | --- |
| 0–4 | $ - | N/A | | | |
| Small 0–100 | $ 450 | $ 450 | $ 600 | $ 1,200 | |
| Small 101–200 | $ 800 | $ 800 | $ 900 | $ 1,800 | |
| Small 201–500 | $ 1,400 | $ 1,400 | $ 1,200 | $ 2,700 | |
| Medium 501–1,000 | $ 2,100 | $ 2,100 | $ 1,800 | $ 3,600 | |
| Medium 1,001–2,000 | $ 3,150 | $ 3,150 | $ 2,400 | $ 5,100 | |
| GTT 2,001–5,000 | $ 4,400 | $ 4,400 | $ 3,300 | $ 7,200 | |
| GTT 5,001–10,000 | $ 6,500 | $ 6,500 | $ 4,800 | $ 9,900 | |
| Large 10,001–20,000 | $ 10,000 | $ 10,000 | $ 6,600 | $ 13,200 | |
| Large 20,001–50,000 | $ 14,000 | $ 14,000 | $ 9,300 | $ 18,600 | |
| Large 50,001–100,000 | $ 21,000 | $ 21,000 | $ 15,000 | $ 27,600 | |
| 100,001 + | custom price | custom price | custom price | custom price | |

**Install Price USD**

| Halo Service Asset Count Tier | Configuration Recon | CVE Recon | Halo Detect | Halo Command (detect is a prerequisite) | Field Authorized Discounts (1 year list 25%) |
| --- | --- | --- | --- | --- | --- |
| 0–4 | $ - | N/A | | | |
| Small 0–100 | $ 450 | $ 450 | $ 900 | $ 2,400 | |
| Small 101–200 | $ 800 | $ 800 | $ 1,350 | $ 3,600 | |
| Small 201–500 | $ 1,400 | $ 1,400 | $ 1,800 | $ 5,400 | |
| Medium 501–1,000 | $ 2,100 | $ 2,100 | $ 2,700 | $ 7,200 | |
| Medium 1,001–2,000 | $ 4,725 | $ 4,725 | $ 6,000 | $ 17,850 | |
| GTT 2,001–5,000 | $ 6,600 | $ 6,600 | $ 8,250 | $ 25,200 | |
| GTT 5,001–10,000 | $ 9,750 | $ 9,750 | $ 12,000 | $ 34,650 | |
| Large 10,001–20,000 | $ 15,000 | $ 15,000 | $ 16,500 | $ 46,200 | |
| Large 20,001–50,000 | $ 35,000 | $ 35,000 | $ 37,200 | $ 111,600 | |
| Large 50,001–100,000 | $ 52,500 | $ 52,500 | $ 60,000 | $ 165,600 | |
| 100,001 + | custom price | custom price | custom price | custom price | |

*Asset count is the sum of firewalls, network devices, endpoints, & servers/VMs detected by Halo from the sources of telemetry ingested.*<br>
*A defense Halo subscription requires selection of one or more services and a tier for each service.*<br>
*Customer required to upgrade to next higher tier if asset count exceeds current tier over two consecutive months.*<br>
*Customer responsible for importing asset profile information into Defense Halo via standard file format.*<br>
*Customer responsible for configuring unmanaged asset data sources to Defense Halo regional collector(s) and GTT responsible for managed asset data sources.*<br>
*Defense Halo Professional Services available to help customers with importing asset profiles and configuring data sources.*

Pricing should be quotable in USD, GBP, and EUR using median exchange rates based on most recent 18 months of history reviewed quarterly.
Have Defense Halo display as a service option available to add to their other managed and unmanaged services as they are quoting them.
Direct and indirect sellers should also be able to quote related but separate subscriptions to Defense Halo Statement of Work (SOW) professional services. These professional services will be custom priced per SOW from standard hourly rates and may include NRR and/or MRR fees.

### SOF
Important terms & conditions for the Halo Service Schedule:
* Billing activates for each service individually 7 days after the first customer data is ingested into the Defense Halo platform for the service allowing for baseline norm learning or 60 days after the initial Defense Halo platform provisioning is complete to avoid unusual customer configuration delays.
* Install delay fees of 75% of impacted Defense Halo service monthly fees will be levied if customer hasn’t successfully configured initial data flows to Defense Halo within 60 days after GTT has completed initial Defense Halo platform provisioning.
* Coterminous with the last service activated.
* Allow in-term upgrades within small, medium, and large tiers but require a re-term when crossing from small to medium tier and medium to large tier.
* Downgrading to the next lower tier invokes a 75% ETF and downgrading more than one-tier in-term is 100% ETF on the delta.
* After the customers excess assets grace period we automatically upgrade them to the next tier?
* Customer can extend the service term of their Defense Halo subscription at any time during a service term or renewal event. The new subscription term applies to all selected services within the subscription.
* Customers can’t reduce an existing Defense Halo subscription service term. Instead, they can terminate individual services or the entire subscription early where early termination fees will apply.
* Customers can’t change the currency used in their Defense Halo subscription and instead they must cancel the existing subscription and replace with a new one of the desired currency.
* Customer can have additional services added to their Defense Halo subscription at any time during a service term or renewal event and the new service inherits the service term of the subscription via a standard established subscription change order process.
* Customer can increase a service tier within their Defense Halo subscription at any time during a service term or renewal event via a standard established subscription change order process.
* Defense Halo subscription automatically renews for month-to-month term unless renewed via sales engagement or notification of subscription termination.
* GTT reserves the right modify pricing over time for new service terms with notice.
* Early termination fees apply when a customer decreases a service tier within their Defense Halo subscription at any time during a service term via a standard established subscription change order process.
* Early termination fees apply when a customer removes a service from their Defense Halo subscription at any time during a service term via a standard established subscription change order process.
* Explicitly disclaim liability for failure to discover all vulnerabilities [KNOWN SITUATION], detect all threats, accurately score all risks, effectively correlate all of the time, and always properly respond to alarms with agents.
* No warranties regarding: accuracy of AI outputs, threat detection efficacy, and completeness of alerts or recommendations.
* Protection of customer data.
* Caps on data ingest rates per asset may limit the context of analysis. / RATE LIMIT / AMOUNT IS SPECIFIED IN THE SERVICE DESCRIPTION/PRODUCT GUIDE
* Customer is responsible for missed alarming of risks due to customer set notification targets and risk thresholds – RISK THRESHOLDS TO SET ALARMS / CHOISES – MADE IN PORTAL
* Customer is responsible for customer user access and chosen authentication methods. ACCESS / CREDENTIALS SINGLE SIGNON – USER HELP GUIDES PRODUCT GUIDE
* Customer is responsible for data sovereignty when selecting regions to have Defense Halo instances installed (EU, UK, US) and their choice of data isolation or correlation across those regions of install.
* GTT IP protection.
* Legal liability relative to mgd service? SLA exclusions?

### SLAs:
* Halo platform services monthly availability of 99.99% (allows ~4 minutes of downtime) with 10% credit of MRR for impacted portion of assets by impacted Halo service(s) when monthly outage time exceeds 4 minutes, 25% credit when exceeding 7 hours, and 50% credit when exceeding 14 hours.
* Failure of high availability GTT managed assets with availability target is as high or higher than the Defense Halo availability target to export configured telemetry to a Defense Halo collector will be counted as downtime against the impacted portion of assets by impacted Defense Halo service(s).
* Downtime of an underlying GTT transport solution carrying customer data to Halo will trigger a Halo availability SLA credit only if its availability target is as high or higher than the Halo availability target, otherwise it will be an excluded event from outage time against the availability SLA target.
* No planned Halo maintenance downtime per month, and any downtime from maintenance counts as outage time against the availability SLA target.

The following table summarizes the outage events counting as downtime against the availability SLA target and some notable exclusions to downtime.

| Service | Downtime Events | Exclusions |
| --- | --- | --- |
| Halo Platform | GTT HA (>99.99%) connection to Halo Collector down<br>GTT Mgd HA (>99.99%) asset fails to export telemetry<br>Halo sending notifications process down | GTT non-HA connect to source data<br>Client connect to Halo collector<br>Client removes Halo access to source data<br>Client notifications receipt failing |
| Halo Portal | Halo Portal down | |
| Halo Recon – Configuration | Halo asset configuration capture process down<br>Halo asset configuration analysis process down<br>Halo configuration risk scoring process down<br>Halo configuration AI recommendations process down | |
| Defense | | |
| Halo Recon – CVE | Halo asset inventory ingest process down<br>Halo CVE capture process down<br>Halo CVE correlation process down<br>Halo CVE Risk scoring process down<br>Halo CVE AI recommendations process down | http://nvd.nist.gov down |
| Halo Detect | Halo asset telemetry capture process down<br>Halo asset telemetry analysis process down<br>Halo event & alarm risk scoring process down<br>Halo alarm AI recommendations process down | |
| Halo Response | Halo agentic response rationale process down<br>Halo agentic response process down<br>Halo agentic response rollback process down | |

* Defense Halo technical support response times acknowledgement within 15 minutes for P1, 2 hours for P2, and 4 business hours for P3 with 10% credit of MRR for impacted Halo services if <95% of tickets in the calendar met the target and 20% credit if <80% met.
* When multiple SLA targets for a Defense Halo service are missed during a service month, the credit percentages are aggregated for the service and then applied against the service MRR for that service month up to a maximum of 50% of MRR for the impacted Halo service.

### Purchase
Not applicable

### Fulfil
Here is the desired standard service order fulfillment process: order PONs in CMD change status to Service Delivery --> assignment of a Project Manager --> assignment of Technical Manager --> upfront customer workshop to complete TAD --> install process initiated.

A Defense Halo TAD must be created by product management and used by the Technical Managers during the upfront customer workshop to collect the following information:
* Targeted asset types and estimated counts.
* Data sources, volumes, connectivity, chosen format standard from the Defense Halo compatible options, and data ingest error notification targets.
* Data sovereignty rules to be compliant with in sourcing and analyzing customer data.
* Selection of Defense Halo instance regions to install in (EU, UK, US) and isolation or correlation across them.
* Standard security frameworks desired from the Defense Halo compatible options for policy analysis.
* Initial set of users and their chosen roles for access to the Defense Halo portal.
* Initial set of notification destinations and thresholds for alarms.
* Chosen alarm thresholds.
* Target turn up date.
* Notes of additional context on the environments to be monitored and analyzed by Defense Halo.

Service delivery coordination and data entry from TAD into CMD and related systems expected to be handled by Project Management in Rod Tilt Organization. 
Desire to use the existing code that turns a SOF into a PON in CMD with oversight and validation by Project Manager.

### Install Process
**Initiate:**
* Defense Halo order management (Order Assure – ~2h)

**Discover:**
* Customer workshop & TAD (Tech Mgr – ~4h)

**Provision:**
* Create Halo instance for customer (AI Eng – ~2h)
* Conf Halo instance settings (AI Eng – ~1h)
* GTT Ops access to Halo instance (AI Eng – ~0.8h)
* GTT Tech Mgr access to Halo instance (AI Eng – ~0.2h)
* Deploy Halo HA Collector pairs (Net Prov – ~0.5h each)
* Conf Halo HA Collector pairs (AI Eng – ~0.5h each)
* Deploy HA virtual firewall pairs (Net Prov – ~0.5h each)
* Conf IPsec on firewall pairs (Net Prov – ~0.5h each)

**Integrate:**
* Customer adds or maps user groups to their IdP
* Customer admins access to Halo admin (Tech Mgr – ~1h)
* Import target mgd asset configs (automatic)
* Customer imports their asset configs
* Conf collector polling of asset conf mods (AI Eng – ~2h)
* Validate ingest of mgd asset inventory (Tech Mgr – ~5h)
* Customer imports their asset inventory
* Conf asset telemetry export to collectors (Net Prov – ~1h)
* Customer confs their asset telemetry exports to collectors
* Customer selects assets for agentic response

**Training:**
* Monitor training of Halo instance (Tech Mgr – ~5h)
* Remediate any go-live issues (Tech Mgr – ~5h)
* Declare Halo instance customer ready (Tech Mgr – ~1h)

**Onboard:**
* Schedule portal training for customer (Proj Mgr – ~1h)
* Customer user access to full Halo portal (Proj Mgr – ~2h)
* Halo portal training for customer (Tech Mgr – ~4h)
* Turnoff alarm/notification suppression (Tech Mgr – ~0.5h)
* Validate alarm/notification receipt (Tech Mgr – ~1h)
* Validate customer can open tickets (Tech Mgr – ~0.5h)

**Go Live:**
* Set start bill date for Halo services (Order Assure – ~0.5h)

Customer training session should be recorded and available to view by new users by link in the customer’s instance of the Halo portal.

### Support
* James Karimi organization to provide 24x7 Defense Halo system administration (restarts, patching, load adjustments, component failovers, backups, component refreshes, etc.).
* James Karimi organization to provide Defense Halo capacity management.
* George Kuzmanovski organization to provide 24x7 Defense Halo customer technical support.
* James Karimi organization to provide Defense Halo continuation engineering (debugging, fixes, pushes, etc.).
* Defense Halo billing support for customers to be provided by the GTT billing support team.
* Defense Halo service terminations to be handled in the GTT standard deprovisioning process.
* Data purging and cleanup following customer departures from Defense Halo to be facilitated by the Defense Halo install team.

### Initial Feature Set / Specific Requirements

| Capabilities (13) | Features (58) | Area |
|---|---|---|
| Defense Halo Platform Customer Tenants | 1) Customer Record 2) Configure Tenant Options 4) Partner | Platform |
| Defense Halo Platform Users and Roles | 1) Customer Users 2) Partner Users 3) GTT Employee Users 4) User Roles | Platform |
| Defense Halo Platform Data Ingest | 1) Flow Telemetry 2) Logs 3) Configurations 4) Configuration Items 5) CVEs | Platform |
| Defense Halo - Regional Availability | 1) Subscription Contracting 2) Collector Deployment | Platform |
| Defense Halo Platform - High Availability | 1) Highly Available 2) BCDR 3) 24x7 Support 4) Capacity Managed 5) Outage-less Releases | Platform |
| Defense Halo Recon - Configuration Service | 1) Security Frameworks 3) Identify Rule Risks 4) Aggregate Risk Score 5) Rule Alarms 7) Dashboard Page 8) Rule Risks Table | Offering |
| Defense Halo Recon - CVE Service | 1) CVE Findings 2) Aggregate Risk Score 3) CVE Alarms 5) Dashboard Page 6) CVE Impacted Assets Table | Offering |
| Defense Halo Detect Service - AI Digital Fingerprinting | 1) Identify 2) Baseline Norms 3) Tuning of Learned Norms | Offering |
| Defense Halo Detect Service - AI Anomaly Inference | 1) Infer Anomalies 2) External Threat Sources 4) Security Classes 6) Risk Score Anomalies 7) Correlate Anomalies into Alarms 8) AI Recommendations 9) Aggregate Risk Scores | Offering |
| Defense Halo Detect Service - Alarm Notifications to Customers | 1) Types of Notification Targets 2) Configure Multiple Alarm Notification Targets 3) Alarm Notification Threshold Settings | Offering |
| Defense Halo Response Service - Agentic Response to Alarms | 1) Agentic Response Segmentation 2) Enable Agentic Response 3) Response Blast Radius Scores 4) Agentic Response Threshold Settings 5) Response Notifications 6) Response Approval Setting | Offering |
| Defense Halo Professional Services | Data Source Integration Service, Asset Inventory Ingest Service, Identity Integration (SSO) Service, Security Posture Optimization Service, Custom Halo Consulting Service | Offering |
| Defense Halo Portal | 1) Isolated Instances 2) Halo Chat 3) Dashboard 4) Analytics Views | Portal to support offerings |

### 1. Defense Halo Platform Customer Tenants
The halo platform should provide complete separation between **customer tenants** by providing each tenant with their own instance of the Halo platform in one or more of the selected regions (EU, UK, US) with the tenant options for isolation or cross correlation along with and GTT partner organization associations when applicable.

#### 1.1 Customer Record
**Feature:** Each customer instance of Halo must be associated with the corresponding customer record in CMD and a region (EU, UK, US).

**Acceptance Criteria:**
- A new customer tenant is only created for a customer in CMD with a newly created Defense Halo service subscription.
- Halo install team can use automation to instantiate an independent tenant of the Halo Platform each Defense Halo subscription.
- Halo install team can use automation tools to deploy a customer’s Halo tenant to the customer chosen region on the TAD from the Halo list of supported regions.
- The initial set of available Halo regions is EU, UK, and US.
- Only those Halo services selected in the customer’s Defense Halo subscription as recorded in CMD are activated in the tenant.

**Constraints:**
- A single Defense Halo subscription per customer can be ordered. { Future desire to support multiple Defense Halo subscriptions per customer up to one in each region of availability. }
- Active services and asset tier changes over time to the customer’s Defense Halo subscription in CMD are inherited by the Halo platform tenant.
- The Halo Platform logs all Halo customer tenant creation and change activities and retains them for 2 years.

**Priority:** Critical

#### 1.2 Configure Tenant Options
**Feature:** The Halo install team must be able to configure settings in each Halo tenant using a Halo Admin panel.

**Acceptance Criteria:**
- The Halo install team can specify regions from the TAD where Halo collectors are to be deployed for the tenant.
- The Halo install team can enter notification targets from the TAD for the tenant.
- The Halo install team can map notification targets to each applicable Halo notification type as specified in the TAD for the tenant.
- The Halo install team can set a single alarm risk score threshold (1 – 100) for the tenant such that only alarms greater than or equal to the threshold level are sent to the mapped notification targets as specified in the TAD for the tenant.
- The Halo install team can set the community intel opt-in option as specified in the TAD for the tenant.

**Constraints:**
- The Halo operations team can modify Halo tenant settings over time.
- The Halo Platform logs all Halo tenant configuration activities and retains for 2 years.

**Priority:** Critical

#### 1.4 Partner Association
**Feature:** Each customer instance of Halo should derive any partner–customer association from the customer’s Defense Halo service instance in CMD and record any such relationship in the Halo Platform to govern any partner user access to the customer’s Halo tenant portal.

**Acceptance Criteria:**
- The Halo Platform records any partner–customer association from the customer’s Defense Halo service instance in CMD.
- An individual partner organization in the Halo Platform may have relationships with zero or more customer tenants at any given time.

**Constraints:**
- The Halo Platform becomes aware of any changes to the partner–customer association over time from CMD and adjusts its recorded relationship accordingly.

**Priority:** High

### 2. Defense Halo Platform Users and Roles

The Halo Platform should only support secure user access via single sign-on (SSO) for customer users, partner users, and GTT employee users that are permissioned via Halo role-based user groups added to their identity provider used to govern access to tenants, the Halo Portal, notifications, and response approvals.

#### 2.1 Customer Users
**Feature:** All customer user access to their Halo tenant should be managed by the customer via adding and removing users to Halo user groups in their identity provider.

**Acceptance Criteria:**
- Customer user access to the Halo platform and portal is constrained to their customer tenant only.
- The Halo platform provides default customer role-based user group names for customers to add to their identity provider when they don’t have strict internal naming conventions.
- The Halo platform provides a method for customers with strict internal naming conventions to map their own group names to the Halo user groups.
- The Halo platform supports customer SSO with identity providers MS Entra ID (50% market adoption) and Okta (20% market adoption).
- The Halo platform supports customer SSO via identity protocols of SAML 2.0 (65% market adoption) and OIDC (35% market adoption).

**Constraints:**
- The Halo platform obtains when available the customer user’s ID, email address, and display name as attributes from SAML or claims from OIDC to use as additional context within the customer’s Halo portal.

**Priority:** Critical

#### 2.2 Partner Users
**Feature:** All partner user access to their customer Halo tenants should be managed by the partner via adding and removing users to Halo user groups in their identity provider.

**Acceptance Criteria:**
- Partner user access is granted to all customer tenant portals associated with the partner organization.
- The Halo platform provides default partner role-based user group names for customers to add to their identity provider when they don’t have strict internal naming conventions.
- The Halo platform provides a method for partners with strict internal naming conventions to map their own group names to the Halo user groups.
- The Halo platform supports partner SSO with identity providers MS Entra ID (50% market adoption) and Okta (20% market adoption).
- The Halo platform supports partner SSO via identity protocols of SAML 2.0 (65% market adoption) and OIDC (35% market adoption).

**Constraints:**
- The Halo platform obtains when available the partner user’s ID, email address, and display name as attributes from SAML or claims from OIDC to use as additional context within each of the partner’s associated customer Halo portals.

**Priority:** High

#### 2.3 GTT Employee Users
**Feature:** All GTT employee access to customer Halo tenants should be managed by the Halo platform administrators via adding and removing GTT employee identities to employee Halo user groups created in GTT’s Microsoft Entra ID account.

**Acceptance Criteria:**
- Employee user access to the Halo platform and portal is granted to individual customer tenants for certain roles while other roles grant access to all customer tenants.
- The Halo platform provides default employee role-based user group names for platform administrators to add to GTT’s Microsoft Entra ID account.
- The Halo platform supports GTT employee SSO with GTT’s Microsoft Entra ID account.
- The Halo platform supports employee SSO via OIDC.

**Constraints:**
- The Halo platform obtains the GTT employee identity’s ID, email address, and display name as attributes as claims from OIDC to use as additional context within the customer Halo portals they have access to.

**Priority:** Critical

#### 2.4 User Roles
**Feature:** The Halo Platform should provide a set of available customer user roles, a set of partner user roles, and a set of GTT employee user roles.

**Acceptance Criteria:**
- GTT employees can be assigned a new Platform Administrator role providing them with permissions to all core Halo Platform functionality and individual customer tenant functionality including administering all users.
- GTT employees can be assigned a new Platform Operations role providing them with permissions to all Halo Platform functionality within each Halo platform customer tenant including administering customer users without any access to core Halo Platform functionality.
- GTT employees can be assigned a new Platform Read-Only role providing them with visibility to all insight views within each Halo platform customer tenant.
- GTT employees can be assigned a new Customer Advocate role providing them with visibility to all insight and some configuration views for specific Halo platform customer tenants that they work with directly.
- Customer users can be assigned a new Customer Administrator role providing them with permissions to all customer Halo Platform functionality within their customer tenant including administering customer users.
- Customer users can be assigned a new Customer SOC role granting them permission to receive alarm response approval notifications with approval and rejection options.
- Customer users can be assigned a new Customer Read-Only role providing them with visibility to all insight views within each Halo platform customer tenant.
- GTT Technical Service Distributor (TSD) users can be assigned a new Partner Admin role providing them with permissions to all Halo Tenants associated with their partner account in Halo.
- GTT Technical Service Distributor (TSD) users can be assigned a new Partner Read-Only role providing them with visibility to all insight views within each Halo tenant associated with their partner account in Halo.

**Constraints:**
- Each user can only have a single Halo role at any given time.
- A user’s assigned Halo role is independent of their assigned EnvisionDX permissions.
- A users assigned role can be changed by users with Customer Administrator, Partner Admin, Customer Advocate, Platform Operations or Platform Administrator role over time.
- GTT employees must request Halo access through standard system access request processes and be granted the appropriate role.
- GTT employees must make separate access requests per tenant for the Customer Advocate and Platform Read-Only roles.

**Priority:** Critical

### 3. Defense Halo Platform Data Ingest

The Halo platform should ingest network flow telemetry, system logs, device policies, asset inventory, and CVEs.

#### 3.1 Flow Telemetry
**Feature:** The Halo platform should be capable of ingesting flow telemetry from GTT managed and unmanaged firewalls, network devices, servers, and VMs.

**Acceptance Criteria:**
- Halo compatibility to ingest: a) NetFlow/IPFIX v9+ (Cisco) – 66% adoption
- Halo remote collector capable of receiving exported flow telemetry via: a) direct UDP push – 55% adoption

**Constraints:**
- Ingest telemetry flow into Halo only within source region, i.e., European Union (EU), United Kingdom (UK), United States (US), Asia Pacific (APAC), and Latin America (LATAM).
- Each Halo customer should have their own instance of a Halo telemetry collector within each region they are providing the telemetry with the raw telemetry never leaving the region and any cross-region correlation of findings data pseudonymized or hashed locally before leaving the region for display in the portal and notifications to ensure regulated data doesn’t leave the region.
- Secure the flow telemetry data while in transit to a Halo collector instance.
- Flow telemetry should be ingested by Halo in near real-time.
- Each customer specific instance of a regional Halo telemetry collector should be scalable up to at least 150,000 flows per second (FPS).
- The following flow telemetry ingest EPS ceilings (firewall – 5,000, network device – 10,000, server – 1,000, cloud – 2,000) are set per asset type and if an asset exceeds 150% of the ceiling for more than five continuous minutes then EPS above the ceiling are dropped.
- Each instance of a Halo telemetry collector should gracefully handle interrupted telemetry flows and subsequently catch up with any source cached flow data once flow is re-established.
- Halo Operations team should be appropriately notified of all errors that occur when Halo attempts to obtain telemetry flow.
- Halo must secure all stored data in its possession until it is properly purged from Halo.
- Halo should retain source telemetry flow data until it has been fully enriched, fingerprinted, inference processed, correlated, and risk scored and then only retain the source telemetry flow directly associated with generated alarms for 30 days before purging.
- Halo should provide near real-time figures on volumes of flow telemetry being ingested so it can be displayed in the Halo portal.

**Priority:** Critical

#### 3.2 Logs
**Feature:** The Halo platform should be capable of ingesting logs from GTT managed and unmanaged firewalls, network devices, servers and VMs.

**Acceptance Criteria:**
- Halo compatibility to ingest: a) Syslog RFC 5424 / 3164 (network, Linux, legacy) – 85% adoption, c) Windows Event (cloud) – 65%
- Halo remote collector capable of receiving exported logs via: a) Syslog-over-TLS using IP Allowlisting & mTLS (network devices) – 80% adoption, b) HTTPS POST (servers) – 65%

**Constraints:**
- Ingest logs into Halo only within source region, i.e., European Union (EU), United Kingdom (UK), United States (US), Asia Pacific (APAC) and Latin America (LATAM).
- Each Halo customer should have their own instance of a Halo log collector within each region they are providing the logs with the raw logs never leaving the region and any cross-region correlation of findings data pseudonymized or hashed locally before leaving the region for display in the portal and notifications to ensure regulated data doesn’t leave the region.
- Secure the log data while in transit to a Halo collector instance.
- Logs should be ingested by Halo in near real-time.
- Each customer specific instance of a regional Halo log collector should be scalable up to at least 150,000 events per second (EPS).
- The following log ingest EPS ceilings (firewall – 1,000, network device – 50, server – 250, endpoint – 25, container – 200, cloud – 75) are set per asset type and if an asset exceeds 150% of the ceiling for more than five continuous minutes then EPS above the ceiling are dropped.
- Each instance of a Halo log collector should gracefully handle interrupted log exports and subsequently catch up with any source cached log data once export is re-established.
- Halo Operations team should be appropriately notified of all errors that occur when Halo attempts to obtain source logs.
- Halo must secure all stored data in its possession until it is properly purged from Halo.
- Halo should retain source log data until it has been fully enriched, fingerprinted, inference processed, correlated, and risk scored and then only retain the source log data directly associated with generated alarms for 30 days before purging.
- Halo should provide near real-time figures on volumes of logs being ingested so it can be displayed in the Halo portal.

**Priority:** Critical

#### 3.3 Configurations
**Feature:** The Halo Portal should facilitate submission of configurations from GTT managed and unmanaged virtual and physical firewalls and network devices on demand for analysis via the Halo Recon – Configuration service.

**Acceptance Criteria:**
- Halo compatibility with firewall and network device configurations for: a) FortiGate G-Series physical, virtual, & cloud – 38% adoption, b) Palo Alto PA & VA-Series physical, virtual, & cloud – 24%, c) Cisco 3100/4200 (FTD 7.x+) physical & virtual – 14%.
- Halo Portal capable of submitting configurations via: a) paste and/or b) upload of extracted configuration files.

**Constraints:**
- Customer user submission of in-region configurations into their in-region Halo Portal instance when tenant is set to region isolation. { GDPR doesn’t require separate regional instances for most configurations, but certain mid-East and APAC do require separate regional instances for submission }.
- Customer user submission of configurations from across regions into their single Halo Portal instance when tenant is set to region correlation.
- Friendly errors communicated when configuration submission encounters any issue.
- Halo must secure all stored configurations in its possession until properly purged from Halo.
- Halo should retain submitted configurations for 1 year.
- Halo should provide near real-time figures on number of configurations analyzed month-to-date so it can be displayed in the Halo portal.

**Priority:** Critical

#### 3.4 Configuration Changes
**Feature:** The Halo platform should be capable of ingesting configuration changes from GTT managed virtual and physical firewalls and network devices for continuous analysis via the Halo Recon – Configuration service.

**Acceptance Criteria:**
- Halo compatibility to ingest GTT managed firewall and network device configurations for: a) FortiGate G-Series physical, virtual, & cloud – 38% adoption, b) Palo Alto PA & VA-Series physical, virtual, & cloud – 24%, and c) Cisco 3100/4200 (FTD 7.x+) physical & virtual – 14% managed through FortiManager, Panorama, Cisco FMC, or GTT Transit Backups.
- Halo collector capable of continuously obtaining configuration changes via API calls to: a) FortiManager, b) Panorama, c) Cisco FMC, and d) GTT Transit Backups.

**Constraints:**
- Ingest configuration changes via Halo Collector only within source region, i.e., European Economic Area (EEA), United Kingdom (UK), United States (US), Asia Pacific (APAC), and Latin America (LATAM).
- Secure the configuration changes while in transit to a Halo collector instance.
- Configurations should be ingested by Halo in near real-time.
- Each customer specific instance of a regional Halo collector should be scalable up to at least 3,000 firewall and network device instances for configuration change capture.
- Each instance of a Halo collector should gracefully handle interrupted access to configuration changes.
- Halo Operations team should be appropriately notified of all errors that occur when Halo attempts to access configuration changes.
- Halo must secure all stored configuration change data in its possession until it is properly purged from Halo.
- Halo should retain collected configuration changes for 1 year.
- Halo should provide near real-time figures on number of assets being monitored for configuration changes so it can be displayed in the Halo portal.

**Priority:** Critical

#### 3.5 Asset Inventory
**Feature:** The Halo platform should be capable of ingesting a Halo tenant’s GTT managed asset inventory from GTT Netbox and non-GTT managed asset inventory from customer imported files to be used in different manners by all four initial Halo services.

**Acceptance Criteria:**
- Halo can ingest asset profiles for: a) the same set of firewalls supported for policy ingest above, b) network devices provided and managed by GTT including EnvisionEdge Gen 5, Cisco ISR (branch), Cisco ASR (aggregator), Accedian NIDs (performance monitoring), Cradlepoint routers (wireless WAN backup), FortiSwitch (LAN device), FortiAP (WAP), c) popular routers & switches including Cisco Catalyst (9000 Series) – 22% adoption, Cisco Nexus (9k/7k/3k) – 18%, Huawei CloudEngine – 14%, Arista 7000 Series – 12%, HPE Aruba (CX Series) – 9%, NVIDIA Spectrum (Mellanox) – 8%, Juniper MX/EX Series – 7%, White Box (SONiC / Bare Metal) – 5%, & Virtual Routers (vCSR, vMX) – 3%.
- Halo can import non-GTT managed provided in a Halo defined CSV file format.
- Halo ingests at least the following profile attributes when available: ID*, Name, Manufacturer*, Product ID, Model #*, Software Version*, Service Pack*, Patch Level*, Activated Services*, Domain Name, IP Address*, MAC Address*, Host Name, Operational Status, Business Criticality, Internet Facing (y/n), Support Group. (* Fields are required).

**Constraints:**
- The asset profile data is secured while in transit to Halo.
- Halo gracefully handles and reports asset inventory ingest errors.
- Halo Operations team notified of all errors that occur when Halo attempts to ingest asset inventory.
- Halo must secure all stored data in its possession until it is properly purged from Halo.
- Halo asset inventory data is retained until deleted by customer or purged by GTT following Halo subscription termination.
- Halo should provide near real-time figures on number of assets in the Halo tenants asset inventory so the figure can be displayed in the Halo portal.
- The asset inventory can be searched and filtered when viewing in the Halo portal.
- Halo allows customer to export their asset inventory to a CSV file.

**Priority:** Critical

#### 3.6 CVEs
**Feature:** The Halo platform should continuously ingest CVEs from the National Vulnerability Database (NVD) at http://nvd.nist.gov for continuous correlation against vulnerability monitored customer assets even when NVD isn’t accessible.

**Acceptance Criteria:**
- Halo ingests new CVEs of any priority or type shortly after initial publishing to correlate against vulnerability monitored assets.

**Constraints:**
- New CVEs should be ingested by Halo within minutes after they are first published.
- Halo should be capable of ingesting at least 1,000 new CVEs per day with a median CVE size of 8 KB. (500 CVEs in one day was the largest spike seen to date with an average daily expected to be around 135).
- Halo high-volume commercial ingestion of CVEs from NVD (up to 50 requests per 30 seconds) requires an API Key; without one, Halo will be subject to lower public rate limits (up to 50 requests per 30 seconds). (NIST reserves the right to monitor API usage to ensure compliance and may block IPs that attempt to circumvent limits.)
- Halo should gracefully handle interrupted NVD access and re-established connection to properly catch up.
- Halo Operations team should be appropriately notified of all errors that occur when Halo attempts to access the NVD.
- Halo should retain CVE data that was correlated with one or more assets for at least 15 months following all CVE monitored assets having been remediated or no longer being observed.
- Halo should provide near real-time figures for the number of assets being monitored for correlated CVEs so it can be displayed in the Halo portal.
- Halo Portal must prominently display: "This product uses the NVD API but is not endorsed or certified by the NVD."

**Priority:** Critical

### 4. Availability

Defense Halo is **availabl****e** in Europe, UK, & US.

#### 4.1 Subscription Contracting
**Feature:** The Halo Response service should be available for subscription contracting in the European Union (EU), United Kingdom (UK), and the United States (US).

**Acceptance Criteria:**
- The Defense Halo service type is available for subscription contracting in the EU, UK, and US.
- All Defense Halo services under the Defense Halo service type are available in the EU, UK, and US.

**Constraints:**
- An individual customer has a single Defense Halo subscription. { Future desire to support multiple Defense Halo subscription up to one region of availability to meet data sovereignty regulations. }
- An individual customer specifies one or more Halo services to be activated within their Defense Halo subscription.

**Priority:** Critical

#### 4.2 Collector Deployment
**Feature:** HA Halo collector pairs for a Halo customer tenant must be available for deployment in the European Union (EU), United Kingdom (UK), United States (US), Asia Pacific (APAC), and Latin America (LATAM).

**Acceptance Criteria:**
- HA Halo collector pairs can be installed in any of the following regions: EU, UK, US, APAC, and LATAM for a Halo tenant.

**Constraints:**
- One or more HA Halo collector pairs can be installed in a region for a Halo tenant as needed to meet the volume of data ingest in that region.

**Priority:** Critical

### 5. Halo Platform

The Defense Halo Platform should be **highly availabl****e** with BCDR & backup, monitored & supported 24x7 with 24x7 service assurance, capacity management, and code updates with outage-less releases.

#### 5.1 High Availability
**Feature:** The Defense Halo AI models, asset inventory, notification engine, admin panel, customer portal, and services should all be highly available.

**Acceptance Criteria:**
- The Defense Halo platform including AI models, asset inventory, notification engine, & admin panel provides 99.99% uptime.
- The Defense Halo portal provides 99.99% uptime.
- The Defense Halo services each provide least 99.99% uptime.
- High availability Recovery Time Objective (RTO) of < 1 minute.
- High availability Recovery Point Objective (RPO) of zero data loss.

**Constraints:**
- Each individual component of Halo provides 99.99% uptime.

**Priority:** Critical

#### 5.2 BCDR
**Feature:** The Defense Halo AI models, asset inventory, notification engine, admin panel, customer portal, and services have business continuity and disaster recovery (BCDR) plans within the regions of availability.

**Acceptance Criteria:**
- The Defense Halo AI models, asset inventory, notification engine, admin panel, customer portal, and services have business continuity and disaster recovery (BCDR) plans within the regions of availability. instances are capable of in-region failover in the EU, UK, US, APAC, & LATAM in the event of an in-region disaster.
- BCDR Recovery Time Objective (RTO) of < 15 minutes.
- BCDR Recovery Point Objective (RPO) of < 1 minute of data loss.

**Constraints:**
- The Defense Halo AI models, asset inventory, notification engine, admin panel, customer portal, and services never failover across regions in order to maintain data sovereignty.
- BCDR failover and failback of all Halo components should be tested in the lab annually.

**Priority:** Critical

#### 5.3 Backup
**Feature:** Customer tenant context, security findings, and Halo transactions should be backed up in region for the duration of their retention periods.

**Acceptance Criteria:**
- Current customer tenant configurations, user preferences, notification targets, approval targets, asset inventory, and agentic templates are backed up throughout the life of the tenant until the Tenant is purged.
- Learned norms and security findings (events, learned norms, anomalies, risk scores, alarms, AI recommendations, agentic responses, and response rationale) are backed up throughout the required retention period of each data type.
- Halo notifications and transaction logs are backed up throughout the required retention period of each data type.

**Constraints:**
- Backup targets are located in separate areas within region.
- Backups occur with frequency necessary to meet Halo high availability and BCDR RPO targets.

**Priority:** Critical

#### 5.4 Monitoring
**Feature:** All Defense Halo components including platform, collectors, virtual firewalls, processes, data stores, portal, services, integrations with other systems, etc. must be monitored for availability, health, and performance.

**Acceptance Criteria:**
- All Defense Halo components including platform, collectors, virtual firewalls, processes, data stores, portal, services, integrations with other systems, etc. are monitored 24x7 for availability, health, and performance.
- All Halo integrations with customer data sources and systems are monitored 24x7 from the Halo side for availability, health, and performance.
- The components monitoring Defense Halo inform the Halo heartbeat section of the Halo Portal that displays near real-time health status of Halo components and services.

**Constraints:**
- Appropriate GTT teams are notified of issues following standard managed service methods and procedures.
- Customer tenants have the option to be notified of Halo element outages, data source access issues, and regional failovers.
- Outages, issues, and failovers are logged and retained for their designated retention period.
- Monitoring logs are accessible by the GTT teams responsible for assessing customer SLA credit requests.

**Priority:** Critical

#### 5.5 Support
**Feature:** All Defense Halo components including platform, collectors, virtual firewalls, processes, data stores, portal, services, integrations with other systems, etc. should be system supported 24x7.

**Acceptance Criteria:**
- All Defense Halo components including platform, collectors, virtual firewalls, processes, data stores, portal, services, integrations with other systems, etc. are supported 24x7 via tickets created in GTT ServiceNow.
- Individual GTT ServiceNow tickets are created per impacted customer for each down-time event per standard managed services practice.

**Constraints:**
- Ticket subclasses are defined in ServiceNow for Defense Halo issue classification.
- Assignment queues are defined in GTT ServiceNow for Defense Halo ticket subclasses.
- The Halo support engineering team is provided with a clearly defined escalation path to other teams for deployment, infrastructure, connectivity, etc. issues that fall outside of their domain of control.
- Response time to Defense Halo issues meet the standard GTT targets of 15 minutes for P1 Critical (Service Down), 2 hours for P2 Degraded (Service Degraded), and 4 hours for P3 Standard (Information or Service Change Requests).

**Priority:** Critical

#### 5.6 Service Assurance
**Feature:** Defense Halo subscribers should receive 24x7 in region service assurance providing technical support for tenant administration, ingesting source data, use of their Halo Portal, receiving alarms, and agentic responses.

**Acceptance Criteria:**
- Users of a Defense Halo subscribing company with access to their Defense Halo portal, EnvisionDX, and/or recorded as a contact in CMD can obtain Service Assurance support for Defense Halo.
- Service Assurance support is accessible through shortcuts in the Defense Halo portal, GTT EnvisionDX portal, by phone via the NOC, by email, or through API integration with their own ticketing systems.
- Service Assurance provides support for tenant administration, ingesting source data, use of their Halo Portal, receiving alarms, and agentic responses.
- Ticket subclasses are defined in ServiceNow for Defense Halo issue classification.
- Assignment queues are defined in GTT ServiceNow for Defense Halo ticket subclasses.
- Service assurance is provided with a clearly defined escalation path to other teams for infrastructure, connectivity, data, AI, and code issues.
- Response time to Defense Halo issues meet the standard GTT targets of 15 minutes for P1 Critical (Service Down), 2 hours for P2 Degraded (Service Degraded), and 4 hours for P3 Standard (Information or Service Change Requests).

**Constraints:**
- GTT Service Assurance exclusively provides Defense Halo support from within the region (EU, UK, US) of the customer’s Defense Halo contract.
- Service Assurance provides standard Defense Halo support in English and additional support in French, German, Italian, and Spanish as a premium service offering as per standard practice for other applicable GTT products.
- Service Assurance doesn’t provide support for assisting with new data source integrations, new asset inventory sources, SSO integrations with new Identity Providers, interpreting Halo security insights, responding to Halo alarms, and guidance on policy changes and response activities from Halo insights. Service Assurance guides customers to their GTT sales or channel partner professional to obtain Help with these items through paid Halo Professional Services.

**Priority:** Critical

#### 5.7 Capacity Managed
**Feature:** All Defense Halo components including platform, collectors, virtual firewalls, processes, data stores, portal, services, integrations with other systems, etc. must be capacity monitored and managed to always ensure sufficient capacity ahead of growing customer demand.

**Acceptance Criteria:**
- All Halo components, processes, data stores, and services are monitored for available capacity relative to tenant demand.
- The AI Engineering team uses capacity monitoring to expand capacity in a timely manner as necessary to stay ahead of growing customer demand.
- The AI Engineering team lifecycle manages legacy capacity refreshes as necessary to maintain competitive service performance.

**Constraints:**
- A financial framework is created and aligned with GTT finance on thresholds of tenants Halo demand as a percentage of available aggregate Halo capacity in each region that when met allow for success based purchase of additional capacity by the AI Engineering team.
- The AI Engineering team is provided with monthly KPIs on Defense Halo services 90 day sales funnel, booked sales, and churn figures for use in calculating demand to capacity thresholds for purchasing more capacity.

**Priority:** Critical

#### 5.8 Outage-less Releases
**Feature:** All Defense Halo components including platform, collectors, virtual firewalls, processes, data stores, portal, services, integrations with other systems, etc. should be updated with outage less releases.

**Acceptance Criteria:**
- All Defense Halo components including platform, collectors, virtual firewalls, processes, data stores, portal, services, etc. can be updated with new infrastructure and code versions without material disruption to data collection, processing, and visualization in the Halo portal user sessions.
- Code updates to Defense Halo components that fail or cause unacceptable issues can quickly be rolled back to prior stable infrastructure and code versions in minutes without material disruption to data collection, processing, and visualization in the Halo portal user sessions.

**Constraints:**
- There is no planned Halo maintenance downtime per month.
- Any downtime from maintenance and upgrades counts as outage time against tenant availability SLA targets.

**Priority:** Critical

### 6. Defense Halo Recon - Configuration

The **Defense Halo Recon – Configuratio****n** service must analyze firewall and network device configurations on demand and continuously monitor subsequent changes against target security frameworks to identify security gaps, assign risk scores, generate alarms, and provide actionable AI guidance for customer resolution.

#### 6.1 Security Frameworks
**Feature:** Customer Administrators must be able to select one or more security frameworks for their tenant to analyze configurations and changes against.

**Acceptance Criteria:**
- The following security frameworks are supported and available for multi-selection for tenants that have activated the Defense Halo Recon – Configuration service: a) NIST Cybersecurity Framework (CSF) 2.0 – 75% adoption, b) CIS Critical Security Controls (v9) – 65%, c) ISO/IEC 27001:2025 – 50%, d) SOC 2 (Type II) – 45%, e) PCI DSS (v4.x) – 35%, and f) NIST SP 800-53 (Rev. 6) – 25%.
- The default selected security framework is NIST Cybersecurity Framework (CSF) 2.0 – 75% adoption.
- All tenant selected security frameworks are displayed in the Halo Dashboard in a manner like the following wireframe.

**Constraints:**
- Halo checks monthly for published updates to the Halo supported security frameworks and updates them in Halo accordingly.

**Priority:** Critical

#### 6.2 Importing Configuration
**Feature:** The Defense Halo Recon – Configuration service must provide a method of uploading and importing configuration files from firewall & network devices via the Halo Portal.

**Acceptance Criteria:**
- Configurations from Cisco, Fortinet, and Palo Alto firewalls and network devices can be ingested.
- An individual configuration file in a .txt, .cfg, and .json format can be uploaded directly into the tenant’s Halo portal for analysis.
- An individual configuration can be imported directly from the source device or native management controller (FortiManager, Panorama, Cisco FMC) directly into the tenant’s Halo portal for analysis by specifying device type, hostname/IP, username, & API key.
- A configuration can be ingested free form without association to any asset in the tenants Halo asset inventory.
- A configuration can be ingested with association to an existing asset in the tenants Halo asset inventory.
- Each free form ingested configuration is counted as an asset for the Defense Halo Recon – Configuration service for the month of ingestion.
- Each configuration ingested for an existing asset in the tenant’s Halo asset inventory is counted as an asset for the Defense Halo Recon – Configuration service for the month of ingestion.

**Constraints:**
- Uploaded and imported configurations are security scanned before they are stored and processed.
- Users uploading and importing configurations into their Halo Portal are provided with friendly messages when ingestion errors are encountered including issues on format, compatibility, syntax, language encoding, size, etc.
- A free form ingested configuration that is a duplicate of a configuration already ingested for the tenant is stored as separate configuration and counted as another asset for the Defense Halo Recon – Configuration service for the month of ingestion.
- When another instance of a configuration is ingested for an asset in the tenant’s asset inventory it is stored as the latest version with prior versions retained but no longer current.
- All compatible and safe configurations are stored in the tenant’s Halo instance.
- Each ingested configuration without continuous monitoring is retained for 2 years from date stored.

**Priority:** Critical

#### 6.3 Configuration Changes
**Feature:** The Defense Halo Recon – Configuration service must provide continuous monitoring of configuration changes for tenant selected compatible firewall & network devices in their Halo asset inventory.

**Acceptance Criteria:**
- Compatible assets in a tenant’s Halo asset inventory can be activated with continuous configuration monitoring and identification of control gaps.
- If an activated asset doesn’t already have an ingested configuration, the current configuration is ingested at the time of enabling by specifying device type, hostname/IP, username, & API key.
- Activated assets are continuously monitored for changes applied to the configuration.
- Detected configuration changes are analyzed.
- Detected configuration changes are applied to the latest version of the asset’s configuration, and a new version of the configuration is created for the asset while retaining previous versions.
- Each activated asset is counted for the Defense Halo Recon – Configuration service starting the month of activation and continuing monthly until deactivated or service terminated.

**Constraints:**
- Continuous configuration monitoring can be deactivated from assets at any time.
- When continuous configuration monitoring is deactivated for an asset the set of previously ingested configuration versions for the asset remain stored for their retention period.
- When continuous configuration monitoring is deactivated for an asset, the asset is no longer counted for the Defense Halo Recon – Configuration service starting the month following deactivation.

**Priority:** Critical

#### 6.4 AI Analysis
**Feature:** The Defense Halo Recon – Configuration service must AI analyze ingested firewall & network device configurations and monitored changes against each tenant selected security framework identifying risk scored compliance control gaps by framework with AI generated resolution guidance for each and calculating a current compliance score by framework for each configuration.

**Acceptance Criteria:**
- Every Halo compatible configuration ingested into Halo is AI analyzed against all controls within tenant selected security frameworks identifying all control gaps by framework.
- Every detected configuration change is AI analyzed against all controls within each tenant selected security framework identifying all control gaps by framework for each change.
- Each identified control gap is risk scored on a scale of 1 (low) to 100 (high) from minor hygiene gaps (1 – 40) to notable misconfigurations (41 – 79) to high risk exposures (80 – 100).
- AI generated resolution guidance is provided for each identified control gap.
- A compliance score is calculated for each ingested configuration on a scale of 0% to 100% using the formula (1 – (failed rules / total rules)) x 100.
- The current compliance score for each ingested configuration is updated when a configuration change is detected and analyzed.

**Constraints:**
- Control gaps are recorded in English language only.
- Control gap risk scores updated when a newer version of a configuration is ingested into Halo and when changes to an ingested configuration are analyzed.
- Configuration compliance scores updated when a newer version of a configuration is ingested into Halo and when changes to an ingested configuration are analyzed.
- Identified control gaps retained for 2 years.
- Each calculated configuration compliance score retained for 2 years.
- Each tenant instance of Halo platform is scalable to handle analysis of a few thousand configuration rules against a dozen security frameworks.

**Priority:** Critical

#### 6.5 Alarms
**Feature:** The Defense Halo Recon – Configuration service must generate alarms for those control gaps with a risk score at or exceeding the tenant’s alarm threshold and send them to those tenant notification targets that are mapped to the control gap alarm notification type.

**Acceptance Criteria:**
- Alarms are created for each individual control gap with a risk score at or exceeding the tenant’s alarm threshold.
- Each alarm includes the analyzed rule, the reference security standard control, description of the gap, risk score, and AI generated resolution guidance.
- Alarms are immediately sent to those tenant notification targets that are mapped to the control gap alarm notification type.

**Constraints:**
- Alarms are created in English language only.
- Alarms are only sent once to notification targets.

**Priority:** Critical

#### 6.6 Risk Score Aggregation
**Feature:** The Defense Halo Recon – Configuration service must aggregate compliance gap risk scores by configuration, asset, and tenant.

**Acceptance Criteria:**
- The Halo platform calculates a rule risk score by firewall policy on a scale of 1 to 100 using capped Root Sum Square (RSS) of individual open rule risk scores for the policy.
- The Halo platform calculates a rule risk score by customer tenant on a scale of 1 to 100 using capped Root Sum Square (RSS) of individual policy risk scores within the tenant.

**Constraints:**
- Each firewall policy risk score is updated when its underlying rules change and when any of the mapped security framework standards change.
- Each customer tenant overall policies risk score is updated when any new firewall policy risk scores are generated or existing ones have changed.
- Halo retains a daily high watermark of policy risk scores and overall policies risk score within each tenant for five years for use in future trending analytics.

**Priority:** Critical

#### 6.7 Portal Display
**Feature:** The Halo Portal must display number of firewalls monitored, number of policies monitored, and number of firewall rule risks within the Estate Context table.

**Acceptance Criteria:**
- The tenant asset inventory can be searched and filtered for those assets with a configuration ingested.
- The tenant asset inventory can be searched and filtered for those assets enabled with configuration change monitoring.
- A table of ingested configurations can be viewed with their current compliance percentage against each security framework.
- The full set of identified control gaps by security framework sorted by risk score from high to low with an alarmed attribute (date/time or null) can be viewed for each configuration.
- A full list of open control gap alarms sorted by risk score high to low can be viewed.
- Control gap alarms are displayed in the full list of open alarms on the Dashboard.
- Halo portal displays running count of alarms notified in the current hour.

**Constraints:**
- Lists of control gaps and alarms are sortable and filterable by risk score, date/time analyzed, configuration, and security framework.
- Displayed control gap information updated only when a newer version of a configuration is ingested into Halo and when changes to an ingested configuration are analyzed.
- Each configuration with its current set of compliance scores against each security framework, list of current alarms, and list of current control gaps & resolution guidance are exportable to a CSV file.

**Priority:** Critical

### 7. **Defense Halo Recon - CVE Service**

The **Defense Halo Recon - CV****E** service delivered through the Halo platform should continuously AI monitor and correlate firewalls and network devices impacted by CVEs providing generative AI guidance to resolve.

#### 7.1 CVE Findings
**Feature:** The Halo Recon - CVE service should continuously check for known CVEs, new CVE monitored assets, and existing monitored assets with configuration changes for each customer tenant to compare against published CVEs generating new CVE findings.

**Acceptance Criteria:**
- Halo platform is aware of new CVEs published on the US National Vulnerability Database (NVD) at https://nvd.nist.gov within minutes after they are first published.
- Halo platform scans all CVE monitored firewall and network devices assets for exposure to newly published CVEs within minutes after CVE awareness.
- Halo platform scans CVEs for newly monitored assets within minutes of asset awareness.
- Halo platform scans CVEs for all CVE monitored assets every hour.
- Halo platform creates a CVE finding for each asset vulnerable to a CVE.
- Halo platform calculates a risk score for each CVE finding on a scale of 1 (lowest risk) to 100 (highest risk).

**Constraints:**
- Each CVE finding remains open until no longer observed.
- The status of each CVE finding is checked every hour.
- The Halo platform retains each CVE finding for at least 15 months following its elimination.
- Halo retains a daily high watermark of # of CVE monitored assets, # of CVE findings, and # of CVE vulnerable assets within each tenant for five years for use in future trending analytics.

**Priority:** Critical

#### 7.2 Aggregate Risk Score
**Feature:** The Halo Recon - CVE service should provide a summarized risk score by individual customer device and an aggregate risk score across all CVE monitored devices for the customer tenant based on open CVE findings.

**Acceptance Criteria:**
- The Halo platform calculates a CVE risk score by vulnerable asset on a scale of 1 to 100 using capped Root Sum Square (RSS) of individual CVE risk scores impacting the asset.
- The Halo platform calculates a CVE risk score by customer tenant on a scale of 1 to 100 using capped Root Sum Square (RSS) of individual asset CVE risk scores within the tenant.

**Constraints:**
- Each asset CVE risk score is updated when new CVE findings are generated and existing CVE findings status changes.
- Each customer tenant overall CVE risk score is updated when any new asset CVE risk scores are generated or existing ones are updated.
- Halo retains a daily high watermark of CVE risk score by asset within each tenant for five years for use in future trending analytics.

**Priority:** Critical

#### 7.3 CVE Alarms
**Feature:** The Halo Recon - CVE service should allow each customer tenant to set a CVE finding risk score threshold for generating CVE alarms from CVE findings and receiving notifications for them to tune the severity and quantity of alarms that are notified and those that are never notified.

**Acceptance Criteria:**
- A single CVE alarm risk threshold can be set within each customer tenant.
- The CVE alarm risk threshold default is 60.
- Customer tenant can change the threshold to an integer value between 1 and 100.
- Any CVE finding risk scored at or above the threshold will generate an alarm for the finding.
- Customer tenant can activate notification of CVE alarms for one or more notification targets.
- Customer tenant can optionally set an hourly maximum CVE alarm budget for each notification target receiving CVE alarms.
- The hourly maximum CVE alarm budget defaults to unlimited for each notification target and can be set to any integer between 1 and 100 or unlimited.
- All generated CVE alarms are notified to configured customer notification targets immediately within the constraints of the hourly maximum CVE alarm budgets.
- Halo portal displays running count of alarms generated in the current hour.
- Halo portal displays running count of alarms notified in the current hour.

**Constraints:**
- The CVE Alarm risk threshold and hourly maximum CVE alarm budget can be changed by customer tenant at any time.
- Halo platform logs all changes to CVE alarm risk threshold and hourly maximum CVE alarm budgets.

**Priority:** Critical

#### 7.5 Dashboard Page
**Feature:** The Dashboard page in the Halo portal should display the # of CVE monitored assets and the number of CVE impacted assets within the Estate Context table.

**Acceptance Criteria:**
- Count figures are displayed in the Estate Context table in a manner like the following wireframe {insert wire frame}
- The number of CVE impacted assets is a link that takes the user to a CVE Impacted Assets Table displayed in a CVE Recon page on the Halo Portal.

**Constraints:**
- Halo portal automatically updates count figures every 5 minutes.

**Priority:** High

#### 7.6 CVE Impacted Assets Table
**Feature:** A CVE Impacted Assets Table should be displayed in a CVE Recon page on the Halo Portal.

**Acceptance Criteria:**
- The CVE Impacted Assets Table displays in a manner like the following wireframe. {insert wireframe}
- The table includes a row per asset and the following columns: risk score, asset, # of findings, and date/time detected

**Constraints:**
- The CVE Impacted Assets Table automatically updates every 5 minutes.

**Priority:** High

### 8. Digital Fingerprint

The Halo Detect service delivered through the Halo platform should AI **digital fingerprin****t** ingested flow telemetry and logs continuously learning and adjusting behavioral norms for traffic, connections, firewalls, network devices, endpoints, servers, VMs, containers, and users within a customer tenant..

#### 8.1 Detect New Assets
**Feature:** The Halo Detect service should continuously automatically identify new assets, connections, traffic patterns, and users for which normal behaviors are to be learned within each customer tenant.

**Acceptance Criteria:**
- New traffic source and destinations are detected from flow telemetry and recorded with attribute enrichment including location when available.
- New firewalls are detected from flow telemetry and logs and recorded with attribute enrichment including location when available.
- New network devices are detected from flow telemetry and logs and recorded with attribute enrichment including location when available.
- New endpoints are detected from flow telemetry and logs and recorded with attribute enrichment including location when available.
- New servers are detected from flow telemetry and logs and recorded with attribute enrichment including location when available.
- New VMs are detected from flow telemetry and logs and recorded with attribute enrichment including location when available.
- New containers are detected from flow telemetry and logs and recorded with attribute enrichment including location when available.
- New users are detected from logs and recorded with attribute enrichment including location when available.
- New asset to asset connections are detected from flow telemetry and logs and recorded with attribute enrichment including ports and protocols when available.
- New user to asset connections are detected from flow telemetry and logs and recorded with attribute enrichment including ports and protocols when available.

**Constraints:**
- Assets, connections, traffic patterns, and users are removed from counts after they are no longer observed in ingested data for a continuous period of 30 days.

**Priority:** Critical

#### 8.2 Learn Baseline Norms
**Feature:** The Halo Detect service should learn baseline norms & relationships for identified new assets, connections, traffic patterns, and users in the days following their initial discovery.

**Acceptance Criteria:**
- Baseline source to destination traffic pattern norms including volumes, packet size, time of day spikes, etc. are learned from flow telemetry over a period of several days after traffic flow initially observed.
- Baseline firewall concurrent connection, connection allows, and connection block volumes, protocol ratios, throughput periodicity, ingress/egress symmetry, time of day, spikes, etc. are learned from flow telemetry and logs over a period of several days after firewall detected.
- Baseline network device connections, ports, protocol ratios, throughput periodicity, ingress/egress symmetry, time of day, spikes, etc. are learned from flow telemetry and logs over a period of several days after device detected.
- Baseline endpoint geolocation, working hours, file access patterns, etc. are learned from logs over a period of several days after initially detected.
- Baseline server process lineage, resource footprint, identity access, etc. are learned from flow telemetry and logs over a period of several days after initially detected.
- Baseline VM process lineage, resource footprint, identity access, etc. are learned from flow telemetry and logs over a period of several days after initially detected.
- Baseline container image integrity, East-West API traffic, environment variable drift, etc. are learned from logs over a period of several days after initially detected.
- Baseline cloud control plane API activity, API call frequency, permission usage, resource spawning, etc. are learned from logs over a period of several days after initially detected.
- Baseline user geolocation, working hours, application & file use, ingress & egress volumes, etc. are learned from logs over a period of several days after initially detected.
- Baseline connection peer-to-peer connections, destinations, frequency, duration, ingress/egress, etc. are learned from flow telemetry and logs over a period of several days after initially detected.

**Constraints:**
- Norms are continuously learned and modified as necessary following changes in observed normal behavior following baseline.

**Priority:** Critical

#### 8.3 Tune Learned Norms
**Feature:** The Halo Detect service should enable customer tuning of learned norms.

**Acceptance Criteria:**
- The Halo portal provides customer tenants with a method of asserting that an alarm is not an anomaly and is normal behavior.
- Chat with Halo feature of the Halo Portal provides a summary of behavior norms for individual assets, connections, traffic patterns, and users when prompted and allows asserting of a learned norm as an anomaly.

**Constraints:**
- Customer asserted norms and anomalies are only changeable by the customer over time and are not changed by continuous Halo platform learning.

**Priority:** High

### 9. Infer Anomalies

The Halo Detect service delivered through the Halo platform should continuously AI **infer anomalie****s** relative to behavior norms, classify those that are security events, correlate them into risk scored alarms with Gen AI recommendations and aggregate them into a single risk score by tenant, asset, user, connection, and destination.

#### 9.1 Infer Anomalies
**Feature:** The Halo Detect service should continuously infer anomalies from flow telemetry and logs ingested by the Halo Platform relative to changing learned norms from digital fingerprinting.

**Acceptance Criteria:**
- Detects anomalies across firewalls, network devices, endpoints, servers, VMs, containers, users, connections, and traffic destinations for the customer estate.
- Detects anomalies from many attributes including date/time, location, origin, destination, quantity, size, spikes, troughs, simultaneous activity, durations, etc.
- Detects behaviors never seen before in asset, user, connectivity, and traffic destination norms.
- Detects behaviors rarely seen before in asset, user, connectivity, and traffic destination norms.
- Detects behaviors that are unusual when seen in asset, user, connectivity, and traffic destination norms.
- Detects behaviors that are naturally suspicious matching known bad patterns in asset, user, connectivity, and traffic destination norms.
- Detects point anomalies of a single occurrence of a behavior.
- Detects contextual anomalies that may be a normal behavior observed in the customer estate but abnormal for a particular asset, user, connectivity, and traffic destination.
- Detects collective anomalies where a sequence of normal point behavior indicates abnormal behavior. Recurring behavior.

**Constraints:**
- Near real-time inference of anomalies.
- Can scale up to 1,000,000 anomalies per day.
- Records all inferred anomalies.
- Retains all inferred anomalies until they are classified.

**Priority:** Critical

#### 9.2 External Threat Sources
**Feature:** The Halo Detect service should access external threat sources within the corresponding commercial rights to train the Halo inference engine and to provide additional context & validation of behavioral anomalies detected to further improve identification of risks.

**Acceptance Criteria:**
- Queries the following external threat sources for use across all Halo customers: a) Abuse.ch/ThreatFox (malware, C2) – free.
- Accesses the following partner threat sources for use with only those Halo customers that have firewall, SDWAN, and SASE solutions from GTT with the necessary licenses in their deployments: a) HPE Aruba's Advanced Threat Defense, b) Fortinet FortiGuard Labs, and c) Palo Alto Networks Unit 42.
- Accesses the Corero SecureWatch Analytics for use with only those Halo customers that have GTT DDoS Protection service.
- Accesses Splunk Threat Intelligence Management (TIM) framework under existing licensing or potentially through expanded licensing if feasible for a period of time to further train the Halo inference engine to the degree allowed by the license.
- Known-malicious indicators (IPs, domains, file hashes, etc.) are used to identify risks.
- Attributes (IPs, domains, file hashes, etc.) of Halo detected anomalies are cross-referenced against threat feeds to further enrich the detected risk.
- Anomalous behavior mapped to specific threat actors or attack techniques in the threat feeds.

**Constraints:**
- The Halo inference engine is further trained from the above external enrichments to the degree allowed by the corresponding commercial licenses.
- Near real-time enrichment.
- Uses caching of prior queries for enrichment where applicable to minimize queries to the external threat source.
- Can scale threat enrichment queries up to 1,000,000 per day.
- Records the use of all external enrichment transactions.
- Retains external enrichment transactions for 180 days.

**Priority:** High

#### 9.4 Classify Anomalies
**Feature:** The Halo Detect service should classify inferred anomalies as security or not and those that are security into security classes & subclasses.

**Acceptance Criteria:**
- A customer’s instance of Halo inference engine classifies inferred anomalies as security related or not. Those that aren’t security related are immediately discarded.
- The security classified anomalies are further classified into one of the following security classifications that is the best match: a) Adversarial AI, b) Cloud, c) Endpoint, d) Identity, e) Infrastructure, or f) Network.
- The Adversarial AI security classified anomalies are further classified into one of the following entity-centric security sub-classifications: a) Direct Prompt Injection – bypass LLM guardrails, b) Indirect Prompt Injection – external data hijacking model instructions, c) Model Evasion – crafted inputs inducing incorrect outputs, or d) Membership Inference – determining if private data trained models.
- The cloud security classified anomalies are further classified into one of the following entity-centric security sub-classifications: a) SaaS Data Movement – mass downloads & unusual sharing, b) Geographic Deviation – access workloads from unusual origin, or c) Cross-App Correlation – user access to workloads from multiple origins in same time frame.
- The endpoint security classified anomalies are further classified into one of the following security sub-classifications based on a "Full Kill-Chain" view: a) Process Genealogy – legitimate processes spawning suspicious processes, b) File System Integrity – file creation in temp & mass file renaming, c) Registry/Persistence – runkeys & service installation for malware persistence, or d) Memory Injection – Shellcode execution, Buffer overflows, Hooking for fileless malware & credential dumping.
- The Identity security classified anomalies are further classified into one of the following security sub-classifications based on compromised credentials rather than malware: a) Logon Hierarchy – source/dest, auth method, success/fail for impossible travel & brute force, b) Privilege Escalation – permission changes, group nesting, admin usage for golden ticket attacks, c) Account Lifecycle – dormant account reactivation, mass password resets for pre-ransomware, or d) Service Principle Activity – api key usage, token theft, malicious automation, cloud service hijacking.
- The infrastructure security classified anomalies are further classified into one of the following configuration-based security sub-classifications: a) Image/Container Escape – malicious breakout from isolated container, b) Unauthorized VM Snapshot – hidden copy of virtual disk, c) Orchestration Hijack – unauthorized control of cluster management, d) Policy Shadowing – new rules hiding existing blocks, or e) Host Resource Exhaustion – denial of service via overconsumption.
- The network security classified anomalies are further classified into one of the following security sub-classifications based on lateral movement and C2 beaconing: a) Traffic Directionality – edge vs internal, lateral movement, data exfiltration, b) Protocol Behavior – DNS query volume, SSH/RDP duration, DNS tunneling, long-lived "Heartbeat" connections, c) Encrypted Traffic Analysis – TLS Fingerprinting, packet length/timing for hidden malware replace channels or d) Entity Discovery – MAC/IP mapping, Hostname, OS Fingerprinting, rogue device detection.

**Constraints:**
- All anomaly classifications happen in near real-time.
- Each customer instance of a Halo inference engine can scale up to at least NNN anomaly classifications per minute.

**Priority:** Critical

#### 9.6 Risk Score Anomalies
**Feature:** The Halo Detect service should risk score anomalies.

**Acceptance Criteria:**
- Correlate across... Pro Tip: When building a risk engine, "Never Seen Before" events should usually be weighted heavily in a Capped RSS model, but only if they correlate with other "Unusual When Seen" events. A single "New Location" is just an alert; a "New Location" + "New Process" + "Rarely Seen Admin replace" is a high-confidence incident.

**Constraints:**
- Accesses the Corero API Telemetry to inform risk-scoring logic for use across all Halo customers.

**Priority:** Critical

#### 9.7 Correlate Anomalies into Alarms
**Feature:** The Halo Detect service should correlate anomalies into alarms.

**Acceptance Criteria:**
- Risk score the correlated alarm by using each individual correlated event risk score as input into a capped RSS calculation with a scale of 0 – 100 where 0 is no risk and 100 is maximum risk.
- High-scoring entities involved in the same timeframe or IP space.
- High-Fidelity Risk Scoring: You aren't just saying "You're under attack." You're saying "You're under an AI-driven Identity attack."

**Priority:** Critical

#### 9.8 Augment Alarms
**Feature:** The Halo Detect service delivered through the Halo platform should Gen AI augment alarms with further context and recommendations to mitigate.

**Acceptance Criteria:**
- AI generated recommendations to further investigate and/or resolve the alarm are included in the alarm.

**Constraints:**
- Certain alarms may not include recommendations in rare occasions when there is lack of AI familiarity with the nature of the alarm.

**Priority:** High

#### 9.9 Aggregate Risk Scores
**Feature:** The Halo Detect service should provide aggregate risk scores by asset, user, connection, destination, site, and tenant.

**Acceptance Criteria:**
- Aggregate by asset, etc.
- Aggregate by tenant using The top $N$ highest-scoring Alarms or Entities (e.g., the Top 5) through Averaged Top-K RSS calculation.

**Priority:** Critical

### 10. Notify Customers of Alarms

The Halo Detect service delivered through the Halo platform should **notify customers of alarm****s** meeting configured thresholds.

#### 10.1 Notification Targets
**Feature:** The Halo Detect service should support alarm notifications to several different types of notification targets to meet common use cases.

**Acceptance Criteria:**
- Email is a supported notification target.
- SMS text is a supported notification target.
- SIEMs is a supported notification target.
- ITSMs is a supported notification target.
- Web Hook

**Constraints:**
- English language only notifications
- Retry if notification fails up to {GTT standard?} attempts
- Inform... when notification attempts error out

**Priority:** Critical

#### 10.2 Configure Notification Targets
**Feature:** The Halo Detect service should allow each customer tenant to configure multiple alarm notification targets of the same or different types and select the class(es) of alarms to be sent to each target.

**Acceptance Criteria:**
- Configure up to N notification targets.
- By default, each target receives all classes of alarms.
- Each target can be configured to only receive a subset of alarm classes.
- Confirm target by sending a test notification to target with a code that is entered into the target configuration prior to the configured target receiving live notifications.
- Simultaneously notify multiple targets with the same alarms.

**Constraints:**
- Customer administrator can pause all notifications to a configured target.
- Customer administrator can resume all notifications to a paused configured target and newly created qualifying alarms will start notifying.
- Customer administrator can modify configuration of targets requiring a reconfirmation test notification.
- Customer administrator can create new notification targets up to maximum allowed.
- Customer administrator can permanently delete notification targets.
- Halo platform logs all customer administrator activity on notification targets.

**Priority:** Critical

#### 10.3 Alarm Notification Threshold Settings
**Feature:** The Halo Detect service should allow each customer tenant to configure alarm notification threshold settings for each notification target to tune the severity and quantity of alarms that are notified and those that are never notified to that target.

**Acceptance Criteria:**
- Service default
- Always send risk score floor
- Never send risk score ceiling
- Maximum alert budget option
- Alarms that aren’t notified...
- Portal displays running count of alarms notified and not notified by severity levels

**Constraints:**
- Change anytime
- Halo platform logs all customer administrator activity on notification targets.

**Priority:** Critical

### 11.  Agentic Responses

The Halo Response service delivered through the Halo platform should provide **agentic respons****e** to alarms from Halo Detect monitored GTT managed assets using agentic templated responses.

#### 11.1 Agentic Response Segmentation
**Feature:** The Halo Response service should provide agentic response segmentation between strategic intent, operational governance, and atomic task execution to provide customers with confidence in Halo handling of complex cross-domain attacks while it maintains segmented control of agents for impact safety.

**Acceptance Criteria:**
- A top tier of agents (meta-agents) manages high-level alarm response missions (ex: ransomware stop) correlating data across subdomains, maintaining a holistic view of an attack chain, deciding what needs to happen at macro level but has no direct write access to tools.
- A middle tier of agents (supervisor agents) translates mission goals from meta-agents into technical plans with tasks within a single security subdomain.
- A low tier of agents (worker agents) executes a single specific atomic task (ex: Block IP) provided by the supervisor agent as an ephemeral process.
- Meta-agents created for the following prominent alarm response missions: see Table A
- Supervisor agents created for the following prominent alarm response mission goals: see Table B
- Worker agents created for the following prominent alarm response missions detectable from flow telemetry and system logs: see table C

**Constraints:**
- A semantic firewall runs between agents to prevent unintended sensitive data from being sent between agents.
- Worker agents output into strict schemas (not natural language) to prevent a hallucination to break the next agent.
- Upfront red team testing of all new agents.
- Shadow mode testing (generated response w/o execution) of new agents or existing agents when LLM model changes for trust baseline validation over 14 to 30 days before live use.
- On-going shadow mode testing of agents performing dynamic autonomous activities to detect agentic drift (compare both agent responses before execution) at a 10% sampling rate and higher sampling rate when agent confidence score drops, LLM updated, or data sources change.
- Shadow mode automated testing for regression (template changes) and environmental calibration (customer environment, LLM) verifying parameter filling, CI data, permissions, and logic shift.
- Scheduled agent credential rotation.
- Every agent should have Just-In-Time (JIT) privileges with no persistent permissions.
- Run all agent-generated code in ephemeral instances.
- Agents retrained or decommissioned when MTTR and correction rate no longer meet accuracy thresholds for the Halo platform.

**Priority:** Critical

#### 11.2 Enable Agentic Response
**Feature:** The Halo Response service should allow each customer tenant to optionally to enable agentic response by asset for each Halo monitored asset.

**Acceptance Criteria:**
- Customer administrators can use the Halo Chat feature to apply response impact sensitivity ratings to their Halo monitored assets.
- Customer users of any role can view the response impact sensitivity ratings by drilling down into the Estate Context table on the Dashboard page in the Defense Halo Portal.

**Constraints:**
- Customer administrators can modify ratings for any monitored asset in their customer tenant.
- Halo platform logs all customer administrator activity on ratings.

**Priority:** Medium

#### 11.3 Response Blast Radius Scores
**Feature:** The Halo Response service should generate response blast radius scores for each supported response capability noted above to be used in agentic decisions on invoking autonomous agent tasks, templated tasks, or HitL tasks.

**Acceptance Criteria:**
- Supervisor agents calculate a blast radius score for each task they define within a task plan for a provided mission goal of an alarm response.
- The blast radius score is calculated as the capped Root Sum Square (RSS) of the task’s base blast radius in the table above and the customer response impact sensitivity rating for each target asset in the task if available.

**Constraints:**
- Halo platform logs all generate blast radius scores.

**Priority:** Critical

#### 11.4 Agentic Response Threshold Settings
**Feature:** The Halo Response service should allow each customer tenant to configure alarm agentic response threshold settings for dynamic autonomous, templated, & HitL responses relative to blast radius scoring of response capabilities.

**Acceptance Criteria:**
- Customer administrators can specify a maximum blast radius score allowing dynamic autonomous agentic alarm response tasks within their customer tenant. The default is 40.
- Customer administrators can specify a maximum blast radius score allowing templated agentic alarm response tasks within their customer tenant. The default is 80. This score must be higher than the maximum score allowing dynamic autonomous agentic alarm response tasks.
- A supervisor agent compares its calculated blast radius score for each planned task against the two thresholds above to determine if the task qualifies for Dynamic Autonomy tasking, template tasking, or falls above the highest threshold and must be HitL tasked.

**Constraints:**
- Customer administrators can modify thresholds for their customer tenant.
- Halo platform logs all customer administrator activity on thresholds.

**Priority:** Critical

#### 11.5 Response Notifications
**Feature:** The Halo Response service should allow each customer tenant to configure alarm response notifications for dynamic autonomous, templated, & HitL responses relative to alarm risk score and blast radius scoring of response capabilities.

**Acceptance Criteria:**
- Customer administrators can specify a minimum alarm risk score within their customer tenant for which Halo responses for alarms scored at and above that level will include notification to the customer. The default is 60.
- Customer administrators can specify a minimum alarm response capability blast radius score within their customer tenant for which Halo response capabilities scored at and above that level will include notification to the customer. The default is 60.
- A supervisor agent compares both the alarm risk score and calculated response capability blast radius score against their corresponding customer thresholds above invoke a notification to the customer on the response activity when either or both thresholds are met or exceeded.
- Notifications are sent to those Halo users in the customer tenant that have enabled alarm response notifications and are sent to the email or SMS text target configured for each user account.
- The notification includes plain-English summary of explainable reasoning of why the response cited with evidence and the nature of the response.

**Constraints:**
- The notification includes plain-English summary of explainable reasoning of why the response cited with evidence and the nature of the response.
- Halo platform logs all customer administrator activity on response notification thresholds.

**Priority:** Critical

#### 11.6 Response Approval Setting
**Feature:** The Halo Response service should allow each customer tenant to configure an alarm response approval setting relative to blast radius scoring that allows Halo to execute a response capability without inline customer approval.

**Acceptance Criteria:**
- Customer administrators can specify a maximum response capability blast radius score allowing Halo response without inline customer approval. The default is 70.
- The response approval setting can’t be lower than the dynamic autonomous threshold setting.
- The response approval setting applies whether the planned response capability involves templated and/or HitL tasks.
- A supervisor agent compares its calculated blast radius score for each planned response capability against the threshold above to determine if request for customer approval should be invoked.
- The approval request includes plain-English summary of explainable reasoning of why the proposed response capability action, cited with evidence.
- Each customer user receiving an email or SMS text has the option to respond with approve or reject actions via an included secure link for each response option.
- Time is of the essence so the first response Halo receives to the approval request whether approval or rejection will determine proceeding with the response capability or halting it and notifying the alarm to the customer for their direct response.

**Constraints:**
- Customer administrators can modify response approval setting for their customer tenant.
- Halo platform logs all customer administrator activity on response approval setting.

**Priority:** Critical

#### 11.7 Custom Response Templates
**Feature:** future feature: The Halo Response service should allow each customer tenant to create their own custom response templates.


Table A:

| Mission | Prominence | Blast Radius | Goals for Supervisor Agents |
|---|---|---|---|
| Triage & Enrichment | 99% (Alert Vol) | 5–15 | Endpoint-Investigative, Network-Investigative, Cloud-Investigative |
| Identity Guard | 90% (Breach Vol) | 30–50 | Identity-Investigative, Identity-Containment |
| Phish-to-Filesystem | 42% (Intrusion) | 20–40 | Endpoint-Investigative, Identity-Investigative, Network-Containment |
| Cloud Leak/Drift | 35% (Cloud Incid) | 50–75 | Endpoint-Containment, Network-Containment, Cloud-Investigative |
| SaaS/Supply Chain | 25% (Emerging) | 40–60 | Cloud-Investigative, Cloud-Remediation, Network-Investigative |
| Ransomware Stop | 18% (Critical) | 60–85 | Identity-Investigative, Endpoint-Investigative, Cloud-Investigative |
| DDoS/Bot Defense | 12% (Disruptive) | 70–90 | Network-Investigative, Network-Remediation, Cloud-Remediation |

Table B:

| Capability | Prominence | Base Blast Radius | Worker Agent Tasks |
|---|---|---|---|
| Endpoint-Investigative | Ultra-High | 10 | Fetch process list, retrieve file metadata, query local event logs, check registry keys. |
| Network-Investigative | High | 15 | Pull NetFlow/PCAP, query DNS logs, lookup IP reputation (OTX/VT), trace route path. |
| Identity-Investigative | High | 20 | Audit sign-in geo-location, check MFA enrollment status, query group memberships, pull service principal logs. |
| Cloud-Investigative | Medium | 25 | Enumerate S3 bucket permissions, audit IAM role assumptions, check VPC flow logs, describe instance metadata. |
| Identity-Containment | Medium | 45 | Revoke active OIDC sessions, disable API keys, force password reset, trigger MFA re-enrollment. |
| Network-Containment | Medium | 50 | Apply temporary firewall block, update WAF IP-deny list, null-route malicious traffic, isolate segment. |
| Endpoint-Containment | Low-Medium | 65 | Isolate host from network, kill malicious process by PID/Hash, quarantine file, disable USB ports. |
| Cloud-Remediation | Low | 85 | Modify S3 bucket policy (private), detach IAM policies, terminate/reboot instances, revert RDS snapshots. |
| Network-Remediation | Low | 90 | Update core routing tables, modify permanent ACLs, divert traffic to scrubbing center, reset BGP peering. |

Table C:

| Task | Prominence | Blast Radius | Description |
|---|---|---|---|
| Fetch_Metadata | Ultra-High | 2 | Retrieve file hashes, process IDs, or system info. |
| Query_Logs | Ultra-High | 5 | Search SIEM, EDR, or CloudTrail for specific events. |
| Network_Trace | High | 8 | Perform DNS lookups, traceroutes, or reputation checks. |
| Audit_Permissions | High | 12 | Enumerate IAM roles, group memberships, or ACLs. |
| Capture_Forensics | Medium | 15 | Pull memory dumps, PCAP files, or disk snapshots. |
| Reset_Credential | Medium | 35 | Force a password reset or MFA re-enrollment. |
| Revoke_Session | Medium | 40 | Kill active OIDC/OAuth tokens or web sessions. |
| Update_WAF_Rule | Medium | 45 | Add a temporary IP block to a web application firewall. |
| Apply_ACL_Block | Medium | 50 | Add a temporary "Deny" rule to a network firewall. |
| Quarantine_File | Low-Medium | 55 | Move a malicious file to a restricted vault. |
| Kill_Process | Low-Medium | 60 | Terminate a running process by PID or Name. |
| Isolate_Host | Low | 70 | Disconnect an endpoint from the production VLAN. |
| Modify_Policy | Low | 85 | Change S3 bucket permissions or IAM Trust policies. |
| Terminate_Resource | Low | 95 | Shut down or delete a cloud instance/database. |

### 12. Defense Halo Professional Services

Provide each customer tenant in the Halo Platform with their own isolated portal instance experience with SSO, RBAC, preferences, notifications, logging, and APIs.

#### 12.1 Asset Inventory
**Feature:** Asset Inventory

**Acceptance Criteria:**
- 

**Constraints:**
- 

**Priority:** Critical

#### 12.2 Data Sources
**Feature:** Data Sources

**Acceptance Criteria:**
- 

**Constraints:**
- 

**Priority:** Critical

#### 12.3 Security Improvements
**Feature:** Security Improvements

**Acceptance Criteria:**
- 

**Constraints:**
- 

**Priority:** Critical

### 13. Halo Portal

Provide each customer tenant in the Halo Platform with their own isolated portal instance experience with SSO, RBAC, preferences, notifications, logging, and APIs.

#### 13.1 Isolated Portal Instance
**Feature:** Provide each customer tenant in the Halo Platform with their own isolated portal instance experience with SSO, RBAC, preferences, notifications, logging, and APIs.

**Acceptance Criteria:**
- 

**Constraints:**
- 

**Priority:** Critical

#### 13.2 Halo Chat Feature
**Feature:** The Halo portal should provide a Halo chat feature acting as the primary user interaction experience for drilling into insights, investigating alarms, technical support, administration queries, & platform health across collector, AI, storage, asset inventory, & portal components and ingest, normalization, digital fingerprinting, inference, analysis, risk scoring, correlation, AI recommendation, AI rationalization, and agentic response services.

**Acceptance Criteria:**
- Halo chat responds with general accuracy to all reasonable inquiries on raw data ingested into the tenant instance for the duration of the data retention.
- Halo chat responds with general accuracy to all reasonable inquiries into data displayed within the tenant’s Halo portal for the duration of the data retention.
- Halo chat responds with general accuracy to all reasonable inquiries on investigating Halo generated alarms by the tenant for the duration of the data retention.
- Halo chat responds with general accuracy to all reasonable inquiries on technical support for Halo services and any current or historical support tickets regarding Halo services.
- Halo chat accurately fulfills reasonable requests to create a support ticket relating to Halo services within the tenant.
- Halo chat accurately fulfills reasonable requests to update attributes and notes for a support ticket previously created by the user including the ability to close the ticket.
- Halo chat responds with general accuracy to all reasonable customer admin user inquiries regarding other tenant users use of the Halo portal and services.
- Halo chat responds with general accuracy to all reasonable inquiries on platform health for the tenant, i.e., is a service up or down or experiencing issues, for the duration of the related data retention.

**Constraints:**
- Halo chat has access to all data within the tenant for the duration of its retention including collector, AI processing, storage, asset inventory, & portal components across ingest, normalization, digital fingerprinting, inference, analysis, risk scoring, correlation, AI recommendation, AI rationalization, and agentic response services.
- Halo chat appears prominently on every primary page in the Halo portal without the need to scroll to see it.
- Halo chat is clearly labeled as an AI chat and the statement “Outputs may contain inaccuracies; please verify critical insights before taking action”.
- Halo chat system prompt layer responds to unsupported inquiries with the statement “I can't assist with that request because it falls outside my scope of security operations. I am designed to assist you with insight analysis, alarm investigation, and technical support.”.
- All customer user roles can use Halo chat.
- Halo chat provides a single continuous chat thread retained across user sessions with no ability start or maintain multiple chat threads.
- All interactions in a user’s chat thread are stored and retained for 90 days by default with tenant option to change to 30 days or 1 year.
- All interactions in a user’s chat thread are searchable throughout their retention period.
- All interactions across all user chat threads are searchable by customer admins in the tenant.
- Customer admins in the tenant can download date/time ranges within retention period from user chat sessions in their tenant to fulfill legal hold requirements.

**Priority:** Critical

#### 13.3 Insights Dashboard
**Feature:** The Halo portal should provide an insights dashboard with the customer tenant’s overall estate risk score, top 5 headlines, AI chat with Halo, estate context, top active alarms, and connection map with each providing drill down links.

**Acceptance Criteria:**
- 

**Constraints:**
- 

**Priority:** Critical

#### 13.4 Analytics Views
**Feature:** The Halo portal should provide customer tenants with analytics views of estate risk score, scored alarms, traffic flows, connection & user anomalies, block spikes, host/device risks, firewall gaps, etc.

**Acceptance Criteria:**
- 

**Constraints:**
- 

**Priority:** Critical

#### 13.5 EnvisionDX Portal
**Feature:** EnvisionDX portal should provide a

**Acceptance Criteria:**
- 

**Constraints:**
- 

**Priority:** 

## 🔭 Observability
Covered in the requirements section above.

## 🎨 User Experience
Covered in the requirements section above.

## 💰 Sales
Sales processes to be defined.

## 🫂 Clients
Customers will use a separate Defense Halo portal for service functionality instead of EnvisionDX portal. EnvisionDX may be the front door to access the Defense Halo portal. Some common information such as customer name, ID, sites, cases, etc. to be shared across the two portals.

## 📚 Product Launch Checklist

| Document | Owner | Needs changed/created? | Has been changed/created? |
| --- | --- | --- | --- |
| Service Schedule | Product Manager | Yes | No |
| Service Definition | Product Manager | Yes | No |
| Pitch Deck | Product Manager | Yes | No |
| Data Sheet | Product Manager | Yes | No |
| TAD | Product Manager | Yes | No |
| Sales Training | Product Manager | Yes | No |
| Operations Training | Product Operations | Yes | No |
| Product Advisory | Product Manager | Yes | No |
