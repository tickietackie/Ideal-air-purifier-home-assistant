import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .api import IdealProAPI
from .const import DOMAIN

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            api = IdealProAPI(host)
            try:
                raw = await api.async_handshake_and_read(timeout=2.0)
                if not raw:
                    errors["base"] = "no_response"
            except Exception:
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(title=f"Ideal {host}", data={CONF_HOST: host})

        data_schema = vol.Schema({vol.Required(CONF_HOST, default="192.168.178.112"): str})
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
