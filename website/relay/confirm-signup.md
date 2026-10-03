---
subject: Confirm your Agent Git Lab email
name: Agent Git Lab signup confirmation
category: transactional
required_context:
  - name: confirm_url
    description: Link that verifies this address for Agent Git Lab updates
example_context:
  confirm_url: https://alexeygrigorev.com/cloudflare-agent-git/subscribe/?token=example
---

Confirm your email to get Agent Git Lab experiment updates.

[Verify your email]({{ confirm_url }})

If you didn't request this, ignore this message. You won't join the confirmed list without using the link.
