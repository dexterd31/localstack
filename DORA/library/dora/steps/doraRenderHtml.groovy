def call(String htmlTemplateUrl, Map metrics) {

    return new jte.dora.constants.HtmlRenderer()
        .renderHtml(htmlTemplateUrl, metrics)
}