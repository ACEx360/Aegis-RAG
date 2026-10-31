"""Generator for evaluation/data/phase1_with_headers.json.

Creates a realistic test set of 42 labeled emails (21 phishing, 21 legitimate)
with full RFC headers (Authentication-Results from mx.google.com, Return-Path,
Reply-To), link arrays, and edge cases specified in AGENTS.md §Pass 4b.
"""

from __future__ import annotations

import json
from pathlib import Path


def generate_evaluation_dataset() -> list[dict]:
    dataset = [
        # =====================================================================
        # PHISHING SAMPLES (21)
        # =====================================================================
        {
            "id": "eval-phish-001",
            "label": "phishing",
            "subject": "Security Alert: Verify your PayPal account immediately",
            "sender": "PayPal Service <service@secure-verify-update.com>",
            "body_text": "We detected unauthorized access to your account. Please log in to verify your identity.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@secure-verify-update.com; spf=pass smtp.mailfrom=secure-verify-update.com; dmarc=pass header.from=secure-verify-update.com"},
                {"name": "Return-Path", "value": "<bounces@secure-verify-update.com>"},
                {"name": "From", "value": "PayPal Service <service@secure-verify-update.com>"}
            ],
            "links": [
                {"url": "https://secure-verify-update.com/signin", "text": "https://www.paypal.com/signin"}
            ],
            "scenario": "Attacker-owned domain with SPF/DKIM/DMARC all passing and anchor text showing well-known brand (paypal.com)"
        },
        {
            "id": "eval-phish-002",
            "label": "phishing",
            "subject": "Urgent: Direct Deposit Information Required",
            "sender": "Corporate Payroll <payroll@bounces-sendgrid-alerts.net>",
            "body_text": "Our payment processor experienced an error. Re-enter your routing number to receive your salary.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=fail; spf=softfail smtp.mailfrom=sendgrid.net; dmarc=fail header.from=bounces-sendgrid-alerts.net"},
                {"name": "Return-Path", "value": "<bounces@bounces-sendgrid-alerts.net>"},
                {"name": "From", "value": "Corporate Payroll <payroll@bounces-sendgrid-alerts.net>"}
            ],
            "links": [
                {"url": "http://198.51.100.45/payroll-update", "text": "Update Payroll Direct Deposit"}
            ],
            "scenario": "Phishing using an ESP-looking bounce domain with failed DMARC and IP address link"
        },
        {
            "id": "eval-phish-003",
            "label": "phishing",
            "subject": "Quick help needed on project emergency",
            "sender": "Prof. Sharma <sharma@viit.ac.in>",
            "body_text": "Hi Alpesh, I am stuck in an urgent faculty meeting without access to my card. Could you quickly purchase two Apple gift cards for the department presentation? Reply to me here.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@viit.ac.in; spf=pass smtp.mailfrom=sharma@viit.ac.in; dmarc=pass header.from=viit.ac.in"},
                {"name": "Return-Path", "value": "<sharma@viit.ac.in>"},
                {"name": "Reply-To", "value": "prof.sharma.faculty.viit@gmail.com"},
                {"name": "From", "value": "Prof. Sharma <sharma@viit.ac.in>"}
            ],
            "links": [],
            "scenario": "Compromised known contact with Reply-To change to external personal Gmail"
        },
        {
            "id": "eval-phish-004",
            "label": "phishing",
            "subject": "IT Helpdesk: Mandatory Password & MFA Expiration Notice",
            "sender": "Campus IT Support <it-helpdesk@viit-support.net>",
            "body_text": "Your college portal password will expire in 2 hours. Due to a server migration, you must reply directly to this email with your current password and active 6-digit MFA token to retain access.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=none; dmarc=none"},
                {"name": "Return-Path", "value": "<it-helpdesk@viit-support.net>"},
                {"name": "From", "value": "Campus IT Support <it-helpdesk@viit-support.net>"}
            ],
            "links": [],
            "scenario": "Credential harvesting request with NO links (social engineering via email reply)"
        },
        {
            "id": "eval-phish-005",
            "label": "phishing",
            "subject": "Your Apple ID has been suspended",
            "sender": "Apple Support <support@pаypal.com>",
            "body_text": "Your account was temporarily disabled. Visit our verification center: https://apple.com.verify-login.cc/id",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=fail; spf=fail smtp.mailfrom=evil.net; dmarc=fail"},
                {"name": "From", "value": "Apple Support <support@pаypal.com>"}
            ],
            "links": [
                {"url": "https://apple.com.verify-login.cc/id", "text": "Re-activate Apple ID"}
            ],
            "scenario": "Punycode lookalike domain and subdomain lookalike with failing auth"
        },
        {
            "id": "eval-phish-006",
            "label": "phishing",
            "subject": "DHL Delivery Notice: Package Detention Fee",
            "sender": "DHL Express <notice@dhl-tracking-express.xyz>",
            "body_text": "Your package could not be delivered due to unpaid customs duty of $1.99. Pay immediately to avoid return to sender.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=pass smtp.mailfrom=dhl-tracking-express.xyz; dmarc=none"},
                {"name": "From", "value": "DHL Express <notice@dhl-tracking-express.xyz>"}
            ],
            "links": [
                {"url": "http://dhl-tracking-express.xyz/pay", "text": "Pay Customs Fee"}
            ],
            "scenario": "Package detention fee lure on cheap generic TLD (.xyz) with HTTP link"
        },
        {
            "id": "eval-phish-007",
            "label": "phishing",
            "subject": "Google Workspace: Suspicious Login Prevented",
            "sender": "Google Security <no-reply@accounts.google.com.security-team.org>",
            "body_text": "A foreign device attempted to sign in. Check the activity: http://google.com/url?q=https://phish-harvest.info/auth",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=none; dmarc=none"},
                {"name": "From", "value": "Google Security <no-reply@accounts.google.com.security-team.org>"}
            ],
            "links": [
                {"url": "http://google.com/url?q=https://phish-harvest.info/auth", "text": "Review Sign-In Activity"}
            ],
            "scenario": "Open redirect abuse (google.com/url?q=) pointing to external phish"
        },
        {
            "id": "eval-phish-008",
            "label": "phishing",
            "subject": "Overdue Invoice INV-92819 - Legal Action Pending",
            "sender": "Accounts Receivable <invoicing@supplier-billing-services.com>",
            "body_text": "Invoice #92819 is 45 days past due. Immediate wire settlement of $4,280 is required to avoid collection agency referral.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@supplier-billing-services.com; spf=pass smtp.mailfrom=supplier-billing-services.com; dmarc=pass"},
                {"name": "From", "value": "Accounts Receivable <invoicing@supplier-billing-services.com>"}
            ],
            "links": [
                {"url": "https://supplier-billing-services.com/invoice/INV-92819.pdf.exe", "text": "Download Detailed Invoice PDF"}
            ],
            "scenario": "Urgent financial coercion with disguised executable link"
        },
        {
            "id": "eval-phish-009",
            "label": "phishing",
            "subject": "Microsoft 365: You have 7 pending quarantined messages",
            "sender": "Office365 Admin <postmaster@o365-quarantine-portal.net>",
            "body_text": "Seven incoming business emails are held in quarantine. Review and release them before automatic purge.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=softfail smtp.mailfrom=o365-quarantine-portal.net; dmarc=none"},
                {"name": "From", "value": "Office365 Admin <postmaster@o365-quarantine-portal.net>"}
            ],
            "links": [
                {"url": "http://bit.ly/m365-quarantine-release", "text": "Release Messages to Inbox"}
            ],
            "scenario": "Quarantine lure using URL shortener (bit.ly) and HTTP"
        },
        {
            "id": "eval-phish-010",
            "label": "phishing",
            "subject": "HR Notice: Annual Performance Bonus Allocation",
            "sender": "Human Resources <hr-rewards@corp-portal-login.biz>",
            "body_text": "Please confirm your employee identity to receive your Q4 bonus allocation of $3,500.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=fail; spf=fail; dmarc=fail"},
                {"name": "From", "value": "Human Resources <hr-rewards@corp-portal-login.biz>"}
            ],
            "links": [
                {"url": "https://corp-portal-login.biz/sso/claim", "text": "Claim Performance Bonus"}
            ],
            "scenario": "Authority impersonation (HR) on .biz domain with complete auth failure"
        },
        {
            "id": "eval-phish-011",
            "label": "phishing",
            "subject": "Meta Security: Facebook Page scheduled for deletion",
            "sender": "Facebook Support <support@meta-security-violations.com>",
            "body_text": "Your page infringed our trademark policies. Appeal within 24 hours or your page will be permanently deleted.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=pass smtp.mailfrom=meta-security-violations.com; dmarc=none"},
                {"name": "From", "value": "Facebook Support <support@meta-security-violations.com>"}
            ],
            "links": [
                {"url": "https://meta-security-violations.com/appeal", "text": "Submit Appeal Form"}
            ],
            "scenario": "Brand impersonation (Meta) with fake urgency deadline"
        },
        {
            "id": "eval-phish-012",
            "label": "phishing",
            "subject": "Zoom: Scheduled Meeting has started without you",
            "sender": "Zoom Video <invitations@zoom-meeting-sso.us>",
            "body_text": "Executive Board Meeting is waiting for you in the conference room. Join immediately.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=none; dmarc=none"},
                {"name": "From", "value": "Zoom Video <invitations@zoom-meeting-sso.us>"}
            ],
            "links": [
                {"url": "https://zoom-meeting-sso.us/join/918239128", "text": "https://zoom.us/j/918239128"}
            ],
            "scenario": "Anchor text mismatch: text shows zoom.us but href targets zoom-meeting-sso.us"
        },
        {
            "id": "eval-phish-013",
            "label": "phishing",
            "subject": "IRS Tax Refund Notification: $940.50 Available",
            "sender": "Internal Revenue Service <refunds@irs-tax-gov.org>",
            "body_text": "Your tax refund calculation resulted in an overpayment credit of $940.50. Complete the direct deposit form.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=fail; spf=fail; dmarc=fail"},
                {"name": "From", "value": "Internal Revenue Service <refunds@irs-tax-gov.org>"}
            ],
            "links": [
                {"url": "http://irs-tax-gov.org/efile/form", "text": "Submit Direct Deposit Information"}
            ],
            "scenario": "Government agency impersonation on fake .org domain with failed auth"
        },
        {
            "id": "eval-phish-014",
            "label": "phishing",
            "subject": "DocuSign: Please sign 'Confidential Separation Agreement'",
            "sender": "DocuSign System <docusign@contracts-management-doc.com>",
            "body_text": "Your manager has requested your signature on the attached severance document. View document online.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@contracts-management-doc.com; spf=pass smtp.mailfrom=contracts-management-doc.com; dmarc=pass"},
                {"name": "From", "value": "DocuSign System <docusign@contracts-management-doc.com>"}
            ],
            "links": [
                {"url": "https://contracts-management-doc.com/sign/18928", "text": "https://docusign.net/sign/18928"}
            ],
            "scenario": "High-fear workplace lure with anchor text showing docusign.net"
        },
        {
            "id": "eval-phish-015",
            "label": "phishing",
            "subject": "Netflix: Payment declined - update card to keep watching",
            "sender": "Netflix Billing <info@netflix-billing-alert.com>",
            "body_text": "We were unable to process your monthly subscription fee. Your service will be paused tomorrow.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=softfail smtp.mailfrom=netflix-billing-alert.com; dmarc=none"},
                {"name": "From", "value": "Netflix Billing <info@netflix-billing-alert.com>"}
            ],
            "links": [
                {"url": "http://netflix-billing-alert.com/account", "text": "Update Payment Method"}
            ],
            "scenario": "Subscription cutoff threat with non-HTTPS link"
        },
        {
            "id": "eval-phish-016",
            "label": "phishing",
            "subject": "LinkedIn: Invitation from VP of Engineering",
            "sender": "LinkedIn Messages <connect@linkedin-professional-network.info>",
            "body_text": "You received an invitation to connect on LinkedIn from Sarah Jenkins, VP at Google.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=none; dmarc=none"},
                {"name": "From", "value": "LinkedIn Messages <connect@linkedin-professional-network.info>"}
            ],
            "links": [
                {"url": "https://linkedin-professional-network.info/invite/910", "text": "View Profile & Accept"}
            ],
            "scenario": "Professional networking lure on .info domain"
        },
        {
            "id": "eval-phish-017",
            "label": "phishing",
            "subject": "Urgent: Verify your account immediately",
            "sender": "Alpesh Thool <alpesh.22310727@viit.ac.in>",
            "body_text": "hi\n",
            "raw_headers": [],
            "links": [],
            "scenario": "Minimal text credential harvesting threat subject sent from internal address without auth headers"
        },
        {
            "id": "eval-phish-018",
            "label": "phishing",
            "subject": "Bank of America: Security code request initiated",
            "sender": "BofA Security <alerts@bankofamerica.com.security-verify.net>",
            "body_text": "Did you request a one-time passcode? If not, click below to lock your online banking.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=fail; spf=fail; dmarc=fail"},
                {"name": "From", "value": "BofA Security <alerts@bankofamerica.com.security-verify.net>"}
            ],
            "links": [
                {"url": "http://bankofamerica.com.security-verify.net/lock", "text": "Lock Account"}
            ],
            "scenario": "Bank OTP alert spoof with lookalike subdomain and auth failure"
        },
        {
            "id": "eval-phish-019",
            "label": "phishing",
            "subject": "Amazon: Suspicious order #402-8192817 placed on your card",
            "sender": "Amazon Fraud Department <order-update@amazon-order-verification.co>",
            "body_text": "An order of iPhone 15 Pro ($1,199.00) was placed to an address in Lagos. Cancel order if this was not you.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=pass smtp.mailfrom=amazon-order-verification.co; dmarc=none"},
                {"name": "From", "value": "Amazon Fraud Department <order-update@amazon-order-verification.co>"}
            ],
            "links": [
                {"url": "http://amazon-order-verification.co/cancel?id=402-8192817", "text": "Cancel Unauthorized Order"}
            ],
            "scenario": "Fraud department panic lure with unauthorized purchase notification"
        },
        {
            "id": "eval-phish-020",
            "label": "phishing",
            "subject": "Instagram: Copyright Infringement Claim #8291",
            "sender": "Meta Copyright <help@instagram-infringement-case.com>",
            "body_text": "A post on your account violates digital copyright laws. Submit proof of license within 12 hours.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=none; dmarc=none"},
                {"name": "From", "value": "Meta Copyright <help@instagram-infringement-case.com>"}
            ],
            "links": [
                {"url": "https://instagram-infringement-case.com/appeal", "text": "Submit Objection"}
            ],
            "scenario": "DMCA takedown panic lure with 12 hour ultimatum"
        },
        {
            "id": "eval-phish-021",
            "label": "phishing",
            "subject": "Dropbox: Shared 'Financial Statement Q4' with you",
            "sender": "Dropbox System <notifications@dropbox-file-transfer.link>",
            "body_text": "David Miller shared confidential financial records with you via Dropbox. Sign in to view.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=none; spf=softfail smtp.mailfrom=dropbox-file-transfer.link; dmarc=none"},
                {"name": "From", "value": "Dropbox System <notifications@dropbox-file-transfer.link>"}
            ],
            "links": [
                {"url": "http://dropbox-file-transfer.link/download", "text": "https://dropbox.com/s/financial-q4"}
            ],
            "scenario": "File share lure with anchor text showing dropbox.com but href pointing to .link domain"
        },

        # =====================================================================
        # LEGITIMATE SAMPLES (21)
        # =====================================================================
        {
            "id": "eval-legit-001",
            "label": "legitimate",
            "subject": "Chase Alert: Unusual debit card activity detected",
            "sender": "Chase Fraud Prevention <fraudprevention@chase.com>",
            "body_text": "We noticed a transaction of $142.50 at Shell Oil on your card ending in 4102. If this was you, reply YES. If not, visit chase.com or call the number on the back of your card.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@chase.com; spf=pass smtp.mailfrom=chase.com; dmarc=pass header.from=chase.com"},
                {"name": "Return-Path", "value": "<epayments@chase.com>"},
                {"name": "From", "value": "Chase Fraud Prevention <fraudprevention@chase.com>"}
            ],
            "links": [
                {"url": "https://www.chase.com/secure/fraud-alerts", "text": "chase.com"}
            ],
            "scenario": "Legit-but-alarming: authentic bank fraud alert with passing SPF/DKIM/DMARC and aligned links"
        },
        {
            "id": "eval-legit-002",
            "label": "legitimate",
            "subject": "URGENT: Final Semester Examination Form Submission Deadline",
            "sender": "Exam Cell VIIT <examcell@viit.ac.in>",
            "body_text": "All final year B.Tech students must submit the university examination form by 5:00 PM today. Failure to submit will result in debarment from the winter session.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@viit.ac.in; spf=pass smtp.mailfrom=examcell@viit.ac.in; dmarc=pass header.from=viit.ac.in"},
                {"name": "Return-Path", "value": "<examcell@viit.ac.in>"},
                {"name": "From", "value": "Exam Cell VIIT <examcell@viit.ac.in>"}
            ],
            "links": [
                {"url": "https://erp.viit.ac.in/exams/form2026", "text": "ERP Examination Form"}
            ],
            "scenario": "Legit-but-alarming: college exam deadline notice with high urgency but clean authentication"
        },
        {
            "id": "eval-legit-003",
            "label": "legitimate",
            "subject": "[GitHub] Please reset your password",
            "sender": "GitHub Support <support@github.com>",
            "body_text": "We heard that you lost your GitHub password. Sorry about that! But don't worry, you can use the link below to reset it. If you did not request this, you can safely ignore this email.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@github.com; spf=pass smtp.mailfrom=github.com; dmarc=pass header.from=github.com"},
                {"name": "Return-Path", "value": "<noreply@github.com>"},
                {"name": "From", "value": "GitHub Support <support@github.com>"}
            ],
            "links": [
                {"url": "https://github.com/password_reset?token=a9f8e7d6c5b4", "text": "Reset password"}
            ],
            "scenario": "Legit-but-alarming: password reset requested by user with authentic DMARC pass"
        },
        {
            "id": "eval-legit-004",
            "label": "legitimate",
            "subject": "Alpesh, 15 new job recommendations matching Python Developer",
            "sender": "Naukri Job Alerts <jobalerts@naukri.com>",
            "body_text": "Top recruiters are searching for candidates with your profile in Pune. Review matching openings and apply.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@naukri.com; spf=pass smtp.mailfrom=jobalerts@naukri.com; dmarc=pass header.from=naukri.com"},
                {"name": "Return-Path", "value": "<bounces@tr.naukri.com>"},
                {"name": "From", "value": "Naukri Job Alerts <jobalerts@naukri.com>"}
            ],
            "links": [
                {"url": "https://tr.naukri.com/track?target=https%3A%2F%2Fwww.naukri.com%2Fjob-listings", "text": "View 15 Jobs"}
            ],
            "scenario": "Newsletter with tracking redirect parameter on allowlisted ESP with passing DMARC"
        },
        {
            "id": "eval-legit-005",
            "label": "legitimate",
            "subject": "Community update: AI Engineering Roadmap 2026",
            "sender": "roadmap.sh <updates@roadmap.sh>",
            "body_text": "Here is the newly published AI Engineering roadmap covering agentic architectures, RAG, and fine-tuning.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@roadmap.sh; spf=pass smtp.mailfrom=182910.hubspotemail.net; dmarc=pass header.from=roadmap.sh"},
                {"name": "Return-Path", "value": "<182910@hubspotemail.net>"},
                {"name": "From", "value": "roadmap.sh <updates@roadmap.sh>"}
            ],
            "links": [
                {"url": "https://updates.roadmap.sh/ai-engineer", "text": "time.fyi"}
            ],
            "scenario": "Legit ESP marketing with hubspotemail.net bounce domain and passing DMARC"
        },
        {
            "id": "eval-legit-006",
            "label": "legitimate",
            "subject": "Project sync meeting notes and next steps",
            "sender": "Priya Patel <priya@workspace.example.com>",
            "body_text": "Hey Alpesh, here are the action items from our morning architecture review: 1. Finish Stage 4 evaluation. 2. Prepare report draft.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@workspace.example.com; spf=pass smtp.mailfrom=priya@workspace.example.com; dmarc=pass"},
                {"name": "From", "value": "Priya Patel <priya@workspace.example.com>"}
            ],
            "links": [],
            "scenario": "Routine internal team communication from known contact"
        },
        {
            "id": "eval-legit-007",
            "label": "legitimate",
            "subject": "New assignment: Major Project Phase 1 Submission",
            "sender": "Google Classroom <no-reply@classroom.google.com>",
            "body_text": "Prof. Deshmukh posted a new assignment in Final Year Major Project 2026: Phase 1 Code and Report.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@classroom.google.com; spf=pass smtp.mailfrom=bounces.google.com; dmarc=pass"},
                {"name": "From", "value": "Google Classroom <no-reply@classroom.google.com>"}
            ],
            "links": [
                {"url": "https://classroom.google.com/c/MzE4OTI1/a/ODk1MjM=", "text": "OR_B.Tech Major Project"}
            ],
            "scenario": "Google Classroom notification with bounce domain and non-domain anchor text"
        },
        {
            "id": "eval-legit-008",
            "label": "legitimate",
            "subject": "Competition Launch: Squares in Squares",
            "sender": "Kaggle <no-reply@kaggle.com>",
            "body_text": "Join the latest Kaggle research competition: Squares in Squares. Compete for $50,000 in prizes.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@kaggle.com; spf=pass smtp.mailfrom=scoutcamp.bounces.google.com; dmarc=pass"},
                {"name": "From", "value": "Kaggle <no-reply@kaggle.com>"}
            ],
            "links": [
                {"url": "https://c.gle/kaggle-competition-squares", "text": "kaggle.com"}
            ],
            "scenario": "Kaggle competition launch with Google scoutcamp bounce domain and c.gle shortener"
        },
        {
            "id": "eval-legit-009",
            "label": "legitimate",
            "subject": "Meta Internship Opportunity!",
            "sender": "Team Unstop <noreply@unstop.news>",
            "body_text": "Apply for Meta Summer Internship 2026. Pre-placement offers available for top performers.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@unstop.news; spf=pass smtp.mailfrom=unstop.news; dmarc=pass"},
                {"name": "Reply-To", "value": "support@unstop.com"},
                {"name": "From", "value": "Team Unstop <noreply@unstop.news>"}
            ],
            "links": [
                {"url": "https://unstop.com/internships/meta-2026", "text": "View Details"}
            ],
            "scenario": "Unstop newsletter with matching SLD reply-to (unstop.news -> unstop.com) and passing DMARC"
        },
        {
            "id": "eval-legit-010",
            "label": "legitimate",
            "subject": "Alpesh Vijay Thool shared a chat with you",
            "sender": "Claude <no-reply-claude@mail.anthropic.com>",
            "body_text": "Alpesh Vijay Thool has shared an AI conversation transcript from Claude with you.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@mail.anthropic.com; spf=pass smtp.mailfrom=mail.anthropic.com; dmarc=pass"},
                {"name": "From", "value": "Claude <no-reply-claude@mail.anthropic.com>"}
            ],
            "links": [
                {"url": "https://claude.ai/share/9a8b7c6d", "text": "Open Conversation"}
            ],
            "scenario": "Anthropic Claude shared chat notification with authentic signature"
        },
        {
            "id": "eval-legit-011",
            "label": "legitimate",
            "subject": "Your Amazon.in order #402-1829102-1928301 has shipped",
            "sender": "Amazon.in <ship-confirm@amazon.in>",
            "body_text": "Your package containing 'SanDisk 128GB Flash Drive' has been dispatched via ATS courier.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@amazon.in; spf=pass smtp.mailfrom=amazon.in; dmarc=pass"},
                {"name": "From", "value": "Amazon.in <ship-confirm@amazon.in>"}
            ],
            "links": [
                {"url": "https://www.amazon.in/gp/your-account/order-details?orderID=402-1829102-1928301", "text": "Track Package"}
            ],
            "scenario": "Authentic e-commerce shipment confirmation with matching headers and links"
        },
        {
            "id": "eval-legit-012",
            "label": "legitimate",
            "subject": "[GitHub] Review requested on PR #42: AegisRAG Stage 4",
            "sender": "GitHub Notifications <notifications@github.com>",
            "body_text": "alex-r requested your review on pull request #42 in aegis-security/aegis-core.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@github.com; spf=pass smtp.mailfrom=github.com; dmarc=pass"},
                {"name": "From", "value": "GitHub Notifications <notifications@github.com>"}
            ],
            "links": [
                {"url": "https://github.com/aegis-security/aegis-core/pull/42", "text": "View Pull Request"}
            ],
            "scenario": "Developer notification from GitHub with strict cryptographic alignment"
        },
        {
            "id": "eval-legit-013",
            "label": "legitimate",
            "subject": "Indigo Flight Booking Confirmation - 6E 521 PNQ to DEL",
            "sender": "IndiGo Airlines <reservations@goindigo.in>",
            "body_text": "Thank you for booking with IndiGo. Your PNR is J92K81. Terminal 1, Pune Airport.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@goindigo.in; spf=pass smtp.mailfrom=goindigo.in; dmarc=pass"},
                {"name": "From", "value": "IndiGo Airlines <reservations@goindigo.in>"}
            ],
            "links": [
                {"url": "https://www.goindigo.in/web-checkin.html", "text": "Web Check-In"}
            ],
            "scenario": "Flight itinerary confirmation from airline with clean SPF and DKIM"
        },
        {
            "id": "eval-legit-014",
            "label": "legitimate",
            "subject": "The Batch: Issue 289 - Agentic Evaluation & RAG benchmarks",
            "sender": "DeepLearning.AI <thebatch@deeplearning.ai>",
            "body_text": "In this week's issue: Andrew Ng on measuring factuality in LLM pipelines with NLI verifiers.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@deeplearning.ai; spf=pass smtp.mailfrom=sendgrid.net; dmarc=pass header.from=deeplearning.ai"},
                {"name": "Return-Path", "value": "<bounces@sendgrid.net>"},
                {"name": "From", "value": "DeepLearning.AI <thebatch@deeplearning.ai>"}
            ],
            "links": [
                {"url": "https://www.deeplearning.ai/the-batch/issue-289", "text": "Read Full Issue"}
            ],
            "scenario": "Technical newsletter sent via SendGrid with passing DMARC"
        },
        {
            "id": "eval-legit-015",
            "label": "legitimate",
            "subject": "Invitation: Aegis Major Project Viva Practice @ Mon Nov 3, 2026 2pm",
            "sender": "Google Calendar <calendar-notification@google.com>",
            "body_text": "You have been invited to Aegis Major Project Viva Practice with Prof. Kulkarni and team.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@google.com; spf=pass smtp.mailfrom=bounces.google.com; dmarc=pass"},
                {"name": "From", "value": "Google Calendar <calendar-notification@google.com>"}
            ],
            "links": [
                {"url": "https://calendar.google.com/calendar/event?eid=ODkyODM5", "text": "Join with Google Meet"}
            ],
            "scenario": "Automated Google Calendar event invitation"
        },
        {
            "id": "eval-legit-016",
            "label": "legitimate",
            "subject": "Urgent :Internship opportunity at Manastik Technology",
            "sender": "Internship VIIT <internship@viit.ac.in>",
            "body_text": "Students interested in this opportunity are requested to fill the Google form by tomorrow 10 AM.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@viit.ac.in; spf=pass smtp.mailfrom=internship@viit.ac.in; dmarc=pass"},
                {"name": "From", "value": "Internship VIIT <internship@viit.ac.in>"}
            ],
            "links": [
                {"url": "https://forms.gle/9a8b7c6d5e", "text": "Application Form"}
            ],
            "scenario": "College placement notice with 'Urgent' keyword in subject and Google form link"
        },
        {
            "id": "eval-legit-017",
            "label": "legitimate",
            "subject": "Your Uber receipt for Tuesday evening ride",
            "sender": "Uber Receipts <uber.india@uber.com>",
            "body_text": "Total fare: Rs 149.00. Thank you for riding with Uber in Pune.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@uber.com; spf=pass smtp.mailfrom=uber.com; dmarc=pass"},
                {"name": "From", "value": "Uber Receipts <uber.india@uber.com>"}
            ],
            "links": [
                {"url": "https://riders.uber.com/trips/189281", "text": "View Trip Details"}
            ],
            "scenario": "Standard transaction receipt from ride-sharing service"
        },
        {
            "id": "eval-legit-018",
            "label": "legitimate",
            "subject": "Stack Overflow: Top questions in Python and Machine Learning",
            "sender": "Stack Overflow <do-not-reply@stackoverflow.email>",
            "body_text": "Here are the top voted discussions this week on PyTorch 2.5 and Transformer tokenization limits.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@stackoverflow.email; spf=pass smtp.mailfrom=stackoverflow.email; dmarc=pass"},
                {"name": "From", "value": "Stack Overflow <do-not-reply@stackoverflow.email>"}
            ],
            "links": [
                {"url": "https://stackoverflow.com/questions/tagged/python", "text": "View Questions"}
            ],
            "scenario": "Weekly community digest with aligned email subdomain"
        },
        {
            "id": "eval-legit-019",
            "label": "legitimate",
            "subject": "Spotify: New release from your favorite artist",
            "sender": "Spotify <no-reply@spotify.com>",
            "body_text": "A new track has just been released. Listen now on Spotify.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@spotify.com; spf=pass smtp.mailfrom=spotify.com; dmarc=pass"},
                {"name": "From", "value": "Spotify <no-reply@spotify.com>"}
            ],
            "links": [
                {"url": "https://open.spotify.com/album/3x9182", "text": "Play on Spotify"}
            ],
            "scenario": "Consumer entertainment streaming notification"
        },
        {
            "id": "eval-legit-020",
            "label": "legitimate",
            "subject": "Mahavitaran: Electricity Bill payment confirmation",
            "sender": "MSEDCL E-Bill <ebill@mahadiscom.in>",
            "body_text": "Payment of Rs 1,840 for consumer number 01928172819 received successfully via BillDesk.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@mahadiscom.in; spf=pass smtp.mailfrom=mahadiscom.in; dmarc=pass"},
                {"name": "From", "value": "MSEDCL E-Bill <ebill@mahadiscom.in>"}
            ],
            "links": [
                {"url": "https://wss.mahadiscom.in/wss/receipt?id=9182391", "text": "Download Tax Receipt"}
            ],
            "scenario": "Utility payment confirmation from state electricity board"
        },
        {
            "id": "eval-legit-021",
            "label": "legitimate",
            "subject": "Your next badge is waiting!",
            "sender": "Salesforce Trailhead <trailhead@mail.salesforce.com>",
            "body_text": "Keep your streak alive. Complete the Data Cloud Quick Look module to earn 100 points.",
            "raw_headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass header.i=@mail.salesforce.com; spf=pass smtp.mailfrom=mail.salesforce.com; dmarc=pass"},
                {"name": "From", "value": "Salesforce Trailhead <trailhead@mail.salesforce.com>"}
            ],
            "links": [
                {"url": "https://trailhead.salesforce.com/modules/data-cloud", "text": "Start Module"}
            ],
            "scenario": "Gamified educational newsletter from corporate platform with passing DMARC"
        }
    ]
    return dataset


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "phase1_with_headers.json"
    
    data = generate_evaluation_dataset()
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Generated {len(data)} emails ({sum(1 for d in data if d['label']=='phishing')} phishing, {sum(1 for d in data if d['label']=='legitimate')} legitimate) -> {out_path}")

