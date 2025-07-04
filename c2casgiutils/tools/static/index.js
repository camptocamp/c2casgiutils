import 'https://cdn.jsdelivr.net/npm/@sbrunner/admin-components@0.6.4/dist/main.js';

/**
 * Display headers element.
 */
class Headers extends window.admin.Element {
  render() {
    if (!this.dataSignal) {
      return window.lit.html``;
    }
    const data = this.dataSignal.get();
    if (!data) {
      return window.lit.html``;
    }
    const headers = data.headers
      ? Object.entries(data.headers).map(([key, value]) => window.lit.html`<b>${key}</b>: ${value}`)
      : [];
    const client_info = data.client_info;
    const queryParams = client_info.query_params
      ? Object.entries(client_info.query_params).map(
          ([key, value]) => window.lit.html`<b>${key}</b>: ${value}`,
        )
      : [];
    const pathParams = client_info.path_params
      ? Object.entries(client_info.path_params).map(
          ([key, value]) => window.lit.html`<b>${key}</b>: ${value}`,
        )
      : [];

    return window.lit.html`<table class="table"><tbody>
              <tr>
                <th>Url</th>
                <td>${client_info.url}</td>
              </tr>
              <tr>
                <th>Base&nbsp;Url</th>
                <td>${client_info.base_url}</td>
              </tr>
              <tr>
                <th>Query&nbsp;Params</th>
                <td>${queryParams.map((param) => window.lit.html`${param}<br>`)}</td>
              </tr>
              <tr>
                <th>Path&nbsp;Params</th>
                <td>${pathParams.map((param) => window.lit.html`${param}<br>`)}</td>
              </tr>
              <tr>
                <th>Headers</th>
                <td>${headers.map((header) => window.lit.html`${header}<br>`)}</td>
              </tr>
              </tbody></table>`;
  }
}
window.customElements.define('c2c-headers', Headers);

/**
 * Display get logging level form.
 */
class GetLogs extends window.admin.Form {
  static properties = {
    applicationModule: { type: String, attribute: 'application-module' },
    action: { type: String },
  };

  render() {
    return window.lit.html`
              <form action="${this.action}" @submit="${this.handleSubmit}" method="get">
                <input type="text" class="form-control" name="name" placeholder="Name" value="${this.applicationModule}" required/>
                <button type="submit" class="btn btn-primary">
                  <admin-status .state="${this.stateSignal}"></admin-status> Get
                </button>
              </form>
            `;
  }
}
window.customElements.define('c2c-logging-get', GetLogs);

/**
 * Display set logging level form.
 */
class SetLogs extends window.admin.Form {
  static properties = {
    applicationModule: { type: String, attribute: 'application-module' },
    action: { type: String },
  };

  render() {
    return window.lit.html`
              <form action="${this.action}" @submit="${this.handleSubmit}">
                <input type="text" class="form-control" name="name" placeholder="Name" value="${this.applicationModule}" required />
                <input type="text" class="form-control" name="level" placeholder="Level" value="INFO"
                  title="DEBUG, INFO, WARNING, ERROR, CRITICAL, NOTSET"
                  pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL|NOTSET)$" required
                />
                <button type="submit" class="btn btn-primary">
                  <admin-status .state="${this.stateSignal}"></admin-status> Set
                </button>
              </form>
            `;
  }
}
window.customElements.define('c2c-logging-set', SetLogs);

/**
 * Display logging level.
 */
class Logs extends window.admin.Element {
  render() {
    if (!this.dataSignal) {
      return window.lit.html``;
    }
    const data = this.dataSignal.get();

    if (!data) {
      return window.lit.html``;
    }

    return window.lit.html`${data.name}: ${data.level} (effective level: ${data.effective_level})`;
  }
}
window.customElements.define('c2c-logging', Logs);

/**
 * Display logging overrides.
 */
class LogsOverrides extends window.admin.Element {
  render() {
    if (!this.dataSignal) {
      return window.lit.html``;
    }
    const data = this.dataSignal.get();
    if (!data) {
      return window.lit.html``;
    }

    if (data.overrides.length === 0) {
      return window.lit.html`<p>No overrides found.</p>`;
    }
    return window.lit.html`<p>${data.overrides.map(
      (override) => window.lit.html`${override.name}: ${override.level}<br>`,
    )}</p>`;
  }
}
window.customElements.define('c2c-logging-overrides', LogsOverrides);
