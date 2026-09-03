from flask import Flask, jsonify

from app.database import init_db
from app.errors import ApiError
from app.seed import seed
from app.routers import (
    auth_router,
    org_router,
    profile_router,
    workflows_router,
    backlog_router,
    opportunities_router,
    matches_router,
    reusable_assets_router,
    similarity_router,
    workspace_router,
    review_router,
    feedback_router,
    audit_router,
)


def create_app():
    app = Flask(__name__)
    init_db()
    seed()

    app.register_blueprint(auth_router.bp)
    app.register_blueprint(org_router.bp)
    app.register_blueprint(profile_router.bp)
    app.register_blueprint(workflows_router.bp)
    app.register_blueprint(backlog_router.bp)
    app.register_blueprint(opportunities_router.bp)
    app.register_blueprint(matches_router.bp)
    app.register_blueprint(reusable_assets_router.bp)
    app.register_blueprint(similarity_router.bp)
    app.register_blueprint(workspace_router.bp)
    app.register_blueprint(review_router.bp)
    app.register_blueprint(feedback_router.bp)
    app.register_blueprint(audit_router.bp)

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        response = jsonify(err.to_dict())
        response.status_code = err.status_code
        return response

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        return response

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8100, debug=True)
